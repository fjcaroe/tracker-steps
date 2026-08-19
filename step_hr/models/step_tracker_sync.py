# © 2026 Steps Consulting
# -*- coding: utf-8 -*-
"""Sincronización de solo lectura entre Odoo y el backend de Web Tracker.

Web Tracker (monitoreo GPS de tractores/maquinaria agrícola) corre como una
app aparte con su propia base Postgres y una API HTTP propia (FastAPI). No
comparte base de datos con Odoo, así que en vez de conectarnos directo a su
Postgres, hacemos *pull* periódico contra su API REST y guardamos una copia
local liviana en los modelos step.tracker.* (ver step_tracker.py).

Endpoints confirmados contra el código fuente del frontend de Web Tracker
(src/services/trackerApi.ts, src/pages/OperationsWorkspace.tsx y el antiguo
StatsPage.tsx): POST /auth/login, GET /auth/me, GET /machines, GET /drivers,
GET /cost_centers, GET /fields, GET /sessions_recent?limit=N.

GET /work_orders (listado) NO está confirmado — el frontend solo usa POST
/work_orders y PUT /work_orders/{id} para crear/cerrar partes desde el
celular del operador, nunca para listarlos. _sync_work_orders() intenta ese
endpoint de forma defensiva y sigue sin romper el resto de la sincronización
si no existe; hay que confirmarlo con quien mantiene el backend FastAPI
antes de confiar en esos datos.
"""

import json
import logging
from datetime import datetime

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

try:
    import requests
except ImportError:  # pragma: no cover - requests siempre está en el venv de Odoo
    requests = None

DEFAULT_TIMEOUT = 20
SESSIONS_PAGE_SIZE = 500


class StepTrackerSyncLog(models.Model):
    _name = 'step.tracker.sync.log'
    _description = 'Registro de sincronización con Web Tracker'
    _order = 'create_date desc'

    company_id = fields.Many2one('res.company', string='Empresa', default=lambda self: self.env.company)
    started_at = fields.Datetime(string='Inicio', default=fields.Datetime.now)
    finished_at = fields.Datetime(string='Término')
    status = fields.Selection([('ok', 'Correcto'), ('partial', 'Parcial'), ('error', 'Error')],
                               string='Resultado', default='ok')
    message = fields.Text(string='Detalle / error')
    machines_synced = fields.Integer(string='Máquinas')
    drivers_synced = fields.Integer(string='Conductores')
    fields_synced = fields.Integer(string='Predios')
    sessions_synced = fields.Integer(string='Sesiones')
    work_orders_synced = fields.Integer(string='Partes')


class StepTrackerSync(models.AbstractModel):
    _name = 'step.tracker.sync'
    _description = 'Motor de sincronización con Web Tracker'

    # ------------------------------------------------------------------
    # Config y autenticación
    # ------------------------------------------------------------------
    @api.model
    def _get_company_config(self, company=None):
        company = company or self.env.company
        base_url = (company.step_tracker_base_url or '').strip().rstrip('/')
        if not base_url:
            raise UserError(_(
                'Configura la URL de la API de Web Tracker en '
                'Ajustes > Labores y Tareas > Web Tracker.'
            ))
        return company, base_url

    @api.model
    def _token_param_key(self, company):
        return f'step_tracker.token.{company.id}'

    @api.model
    def _login(self, company, base_url):
        if not (company.step_tracker_username and company.step_tracker_password):
            raise UserError(_(
                'Configura el usuario y la contraseña de servicio de Web Tracker '
                'en Ajustes > Labores y Tareas > Web Tracker.'
            ))
        resp = requests.post(
            f'{base_url}/auth/login',
            json={'username': company.step_tracker_username, 'password': company.step_tracker_password},
            timeout=DEFAULT_TIMEOUT,
        )
        resp.raise_for_status()
        token = resp.json().get('access_token')
        if not token:
            raise UserError(_('Web Tracker no devolvió un token de acceso válido.'))
        self.env['ir.config_parameter'].sudo().set_param(self._token_param_key(company), token)
        return token

    @api.model
    def _get_token(self, company, base_url, force_refresh=False):
        param_key = self._token_param_key(company)
        if not force_refresh:
            token = self.env['ir.config_parameter'].sudo().get_param(param_key)
            if token:
                return token
        return self._login(company, base_url)

    @api.model
    def _get_json(self, company, base_url, path, params=None):
        if requests is None:
            raise UserError(_('El paquete Python "requests" no está disponible en este servidor de Odoo.'))
        token = self._get_token(company, base_url)
        resp = requests.get(
            f'{base_url}{path}',
            headers={'Authorization': f'Bearer {token}'},
            params=params,
            timeout=DEFAULT_TIMEOUT,
        )
        if resp.status_code == 401:
            token = self._get_token(company, base_url, force_refresh=True)
            resp = requests.get(
                f'{base_url}{path}',
                headers={'Authorization': f'Bearer {token}'},
                params=params,
                timeout=DEFAULT_TIMEOUT,
            )
        resp.raise_for_status()
        return resp.json()

    # ------------------------------------------------------------------
    # Punto de entrada (botón "Sincronizar ahora" y cron)
    # ------------------------------------------------------------------
    @api.model
    def run_sync(self, raise_on_error=True):
        company, base_url = self._get_company_config()
        log = self.env['step.tracker.sync.log'].sudo().create({'company_id': company.id})
        counts = {'machines': 0, 'drivers': 0, 'fields': 0, 'sessions': 0, 'work_orders': 0}
        errors = []

        for key, method in (
            ('machines', self._sync_machines),
            ('drivers', self._sync_drivers),
            ('fields', self._sync_fields),
            ('sessions', self._sync_sessions),
        ):
            try:
                counts[key] = method(company, base_url)
            except Exception as exc:  # noqa: BLE001 - errores de red/API no deben tumbar todo el cron
                _logger.exception('step.tracker.sync: falló %s', key)
                errors.append(f'{key}: {exc}')

        # /work_orders (listado) no está confirmado contra el backend real: se intenta
        # aparte y nunca hace fallar la sincronización de maestros/sesiones.
        try:
            counts['work_orders'] = self._sync_work_orders(company, base_url)
        except Exception as exc:  # noqa: BLE001
            _logger.warning('step.tracker.sync: /work_orders no disponible o con otro formato: %s', exc)
            errors.append(f'work_orders (no confirmado): {exc}')

        status = 'ok' if not errors else ('error' if len(errors) == 5 else 'partial')
        log.write({
            'finished_at': fields.Datetime.now(),
            'status': status,
            'message': '\n'.join(errors) or False,
            'machines_synced': counts['machines'],
            'drivers_synced': counts['drivers'],
            'fields_synced': counts['fields'],
            'sessions_synced': counts['sessions'],
            'work_orders_synced': counts['work_orders'],
        })

        if raise_on_error and status == 'error':
            raise UserError(_('La sincronización con Web Tracker falló:\n%s') % '\n'.join(errors))
        return counts

    # ------------------------------------------------------------------
    # Sincronización por entidad (upsert por tracker_id + company_id)
    # ------------------------------------------------------------------
    @staticmethod
    def _parse_dt(value):
        """ISO 8601 (con 'Z' u offset) -> datetime naive en UTC, como espera Odoo."""
        if not value:
            return False
        try:
            dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
        except ValueError:
            return False
        if dt.tzinfo is not None:
            dt = datetime(*dt.utctimetuple()[:6])
        return fields.Datetime.to_string(dt)

    @api.model
    def _upsert(self, model_name, company, tracker_id, values):
        Model = self.env[model_name].sudo()
        record = Model.search([('tracker_id', '=', tracker_id), ('company_id', '=', company.id)], limit=1)
        values = dict(values, tracker_id=tracker_id, company_id=company.id)
        if record:
            record.write(values)
        else:
            record = Model.create(values)
        return record

    @api.model
    def _sync_machines(self, company, base_url):
        data = self._get_json(company, base_url, '/machines')
        now = fields.Datetime.now()
        for item in data:
            self._upsert('step.tracker.machine', company, item['id'], {
                'name': item.get('name') or _('Máquina %s') % item['id'],
                'plate': item.get('plate'),
                'external_id': item.get('external_id'),
                'active': item.get('is_active', True),
                'tank_capacity_liters': item.get('tank_capacity_liters') or 0.0,
                'fuel_consumption_lph': item.get('fuel_consumption_lph') or 0.0,
                'fuel_consumption_lpkm': item.get('fuel_consumption_lpkm') or 0.0,
                'last_sync': now,
            })
        return len(data)

    @api.model
    def _sync_drivers(self, company, base_url):
        data = self._get_json(company, base_url, '/drivers')
        now = fields.Datetime.now()
        for item in data:
            self._upsert('step.tracker.driver', company, item['id'], {
                'name': item.get('name') or _('Conductor %s') % item['id'],
                'rut': item.get('rut'),
                'active': item.get('is_active', True),
                'last_sync': now,
            })
        return len(data)

    @api.model
    def _sync_fields(self, company, base_url):
        data = self._get_json(company, base_url, '/fields')
        now = fields.Datetime.now()
        for item in data:
            self._upsert('step.tracker.field', company, item['id'], {
                'name': item.get('name') or _('Predio %s') % item['id'],
                'color': item.get('color'),
                'cost_center_tracker_id': item.get('cost_center_id') or 0,
                'polygon_json': json.dumps(item.get('polygon') or []),
                'last_sync': now,
            })
        return len(data)

    @api.model
    def _sync_sessions(self, company, base_url):
        data = self._get_json(company, base_url, '/sessions_recent', params={'limit': SESSIONS_PAGE_SIZE})
        MachineLink = self.env['step.tracker.machine'].sudo()
        for item in data:
            machine = MachineLink.search([
                ('tracker_id', '=', item.get('machine_id')), ('company_id', '=', company.id),
            ], limit=1)
            self._upsert('step.tracker.session', company, str(item['id']), {
                'machine_id': machine.id if machine else False,
                'started_at': self._parse_dt(item.get('started_at')),
                'ended_at': self._parse_dt(item.get('ended_at')),
                'status': item.get('status') or 'open',
                'points_count': item.get('points_count') or 0,
                'total_distance_km': (item.get('total_distance_m') or 0) / 1000.0,
                'avg_speed_kmh': item.get('avg_speed_kmh') or 0.0,
                'work_order_tracker_id': item.get('work_order_id') or 0,
            })
        return len(data)

    @api.model
    def _sync_work_orders(self, company, base_url):
        data = self._get_json(company, base_url, '/work_orders')
        MachineLink = self.env['step.tracker.machine'].sudo()
        for item in data:
            machine = MachineLink.search([
                ('tracker_id', '=', item.get('machine_id')), ('company_id', '=', company.id),
            ], limit=1)
            self._upsert('step.tracker.work_order', company, item['id'], {
                'code': item.get('code'),
                'work_date': item.get('work_date'),
                'machine_id': machine.id if machine else False,
                'hourmeter_initial': item.get('hourmeter_initial') or 0.0,
                'hourmeter_final': item.get('hourmeter_final') or 0.0,
                'fuel_tank_start_liters': item.get('fuel_tank_start_liters') or 0.0,
                'fuel_tank_end_liters': item.get('fuel_tank_end_liters') or 0.0,
                'fuel_refill_liters': item.get('fuel_refill_liters') or 0.0,
            })
        return len(data)
