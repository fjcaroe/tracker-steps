# © 2026 Steps Consulting
# -*- coding: utf-8 -*-
"""Sincronización de solo lectura entre Odoo y el backend de Web Tracker.

Web Tracker (monitoreo GPS de tractores/maquinaria agrícola) corre como una
app aparte con su propia base Postgres y una API HTTP propia (FastAPI). No
comparte base de datos con Odoo, así que en vez de conectarnos directo a su
Postgres, hacemos *pull* periódico contra su API REST y guardamos una copia
local liviana en los modelos step.tracker.* (ver step_tracker.py).

Endpoints confirmados contra el backend versionado en backend/tracker_py y el
frontend de Web Tracker: POST /auth/login, GET /auth/me, GET /machines,
GET /drivers, GET /cost_centers, GET /fields, GET /sessions_recent?limit=N.
GET /health/capabilities identifica el release y los contratos administrativos
disponibles antes de actualizar este módulo en GCP.

GET /work_orders (listado) y sus contratos de alta/edición están versionados
en backend/tracker_py. WorkOrderOut incluye machine_id y todas las lecturas de
combustible desde el release 2026.08.20.
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
REQUIRED_CAPABILITIES = {
    'odoo_sync_v1',
    'master_drivers_crud',
    'master_activities_crud',
    'master_labors_crud',
    'master_implements_crud',
    'master_fields_polygon_crud',
    'work_orders_manual_crud',
}


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
    activities_synced = fields.Integer(string='Actividades')
    labors_synced = fields.Integer(string='Labores')
    implements_synced = fields.Integer(string='Implementos')
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

    @api.model
    def _check_api_compatibility(self, base_url):
        if requests is None:
            raise UserError(_('El paquete Python "requests" no está disponible en este servidor de Odoo.'))
        resp = requests.get(f'{base_url}/health/capabilities', timeout=DEFAULT_TIMEOUT)
        if resp.status_code == 404:
            raise UserError(_(
                'La API de Web Tracker está desactualizada: no publica '
                '/health/capabilities. Despliega primero el backend requerido.'
            ))
        resp.raise_for_status()
        advertised = set(resp.json().get('capabilities') or [])
        missing = sorted(REQUIRED_CAPABILITIES - advertised)
        if missing:
            raise UserError(_(
                'La API de Web Tracker no tiene todas las capacidades requeridas: %s'
            ) % ', '.join(missing))

    # ------------------------------------------------------------------
    # Punto de entrada (botón "Sincronizar ahora" y cron)
    # ------------------------------------------------------------------
    @api.model
    def run_sync(self, raise_on_error=True):
        company, base_url = self._get_company_config()
        log = self.env['step.tracker.sync.log'].sudo().create({'company_id': company.id})
        counts = {
            'machines': 0, 'drivers': 0, 'activities': 0, 'labors': 0,
            'implements': 0, 'fields': 0, 'sessions': 0, 'work_orders': 0,
        }
        errors = []

        try:
            self._check_api_compatibility(base_url)
        except Exception as exc:  # noqa: BLE001
            log.write({
                'finished_at': fields.Datetime.now(),
                'status': 'error',
                'message': str(exc),
            })
            if raise_on_error:
                raise UserError(_('La API de Web Tracker no es compatible:\n%s') % exc) from exc
            return counts

        sync_methods = (
            ('machines', self._sync_machines),
            ('drivers', self._sync_drivers),
            ('activities', self._sync_activities),
            ('labors', self._sync_labors),
            ('implements', self._sync_implements),
            ('fields', self._sync_fields),
            ('sessions', self._sync_sessions),
            ('work_orders', self._sync_work_orders),
        )
        for key, method in sync_methods:
            try:
                counts[key] = method(company, base_url)
            except Exception as exc:  # noqa: BLE001 - errores de red/API no deben tumbar todo el cron
                _logger.exception('step.tracker.sync: falló %s', key)
                errors.append(f'{key}: {exc}')

        status = 'ok' if not errors else ('error' if len(errors) == len(sync_methods) else 'partial')
        log.write({
            'finished_at': fields.Datetime.now(),
            'status': status,
            'message': '\n'.join(errors) or False,
            'machines_synced': counts['machines'],
            'drivers_synced': counts['drivers'],
            'activities_synced': counts['activities'],
            'labors_synced': counts['labors'],
            'implements_synced': counts['implements'],
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
    def _sync_activities(self, company, base_url):
        data = self._get_json(company, base_url, '/activities', params={'include_inactive': True})
        now = fields.Datetime.now()
        for item in data:
            self._upsert('step.tracker.activity', company, item['id'], {
                'name': item.get('name') or _('Actividad %s') % item['id'],
                'code': item.get('code'),
                'active': item.get('is_active', True),
                'last_sync': now,
            })
        return len(data)

    @api.model
    def _sync_labors(self, company, base_url):
        data = self._get_json(company, base_url, '/labors', params={'include_inactive': True})
        ActivityLink = self.env['step.tracker.activity'].sudo()
        now = fields.Datetime.now()
        for item in data:
            activity = ActivityLink.search([
                ('tracker_id', '=', item.get('activity_id')), ('company_id', '=', company.id),
            ], limit=1)
            self._upsert('step.tracker.labor', company, item['id'], {
                'name': item.get('name') or _('Labor %s') % item['id'],
                'code': item.get('code'),
                'activity_id': activity.id if activity else False,
                'activity_tracker_id': item.get('activity_id') or 0,
                'effort_factor': item.get('effort_factor') or 0.0,
                'target_speed_kmh': item.get('target_speed_kmh') or 0.0,
                'active': item.get('is_active', True),
                'last_sync': now,
            })
        return len(data)

    @api.model
    def _sync_implements(self, company, base_url):
        data = self._get_json(company, base_url, '/implements', params={'include_inactive': True})
        now = fields.Datetime.now()
        for item in data:
            self._upsert('step.tracker.implement', company, item['id'], {
                'name': item.get('name') or _('Implemento %s') % item['id'],
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
        DriverLink = self.env['step.tracker.driver'].sudo()
        FieldLink = self.env['step.tracker.field'].sudo()
        for item in data:
            machine = MachineLink.search([
                ('tracker_id', '=', item.get('machine_id')), ('company_id', '=', company.id),
            ], limit=1)
            driver = DriverLink.search([
                ('tracker_id', '=', item.get('driver_id')), ('company_id', '=', company.id),
            ], limit=1)
            field = FieldLink.search([
                ('cost_center_tracker_id', '=', item.get('cost_center_id')),
                ('company_id', '=', company.id),
            ], limit=1)
            self._upsert('step.tracker.session', company, str(item['id']), {
                'machine_id': machine.id if machine else False,
                'driver_id': driver.id if driver else False,
                'analytic_account_id': field.analytic_account_id.id if field and field.analytic_account_id else False,
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
        ActivityLink = self.env['step.tracker.activity'].sudo()
        LaborLink = self.env['step.tracker.labor'].sudo()
        ImplementLink = self.env['step.tracker.implement'].sudo()
        FieldLink = self.env['step.tracker.field'].sudo()
        for item in data:
            machine = MachineLink.search([
                ('tracker_id', '=', item.get('machine_id')), ('company_id', '=', company.id),
            ], limit=1)
            activity = ActivityLink.search([
                ('tracker_id', '=', item.get('activity_id')), ('company_id', '=', company.id),
            ], limit=1)
            labor = LaborLink.search([
                ('tracker_id', '=', item.get('labor_id')), ('company_id', '=', company.id),
            ], limit=1)
            implement = ImplementLink.search([
                ('tracker_id', '=', item.get('implement_id')), ('company_id', '=', company.id),
            ], limit=1)
            field = FieldLink.search([
                ('tracker_id', '=', item.get('field_id')), ('company_id', '=', company.id),
            ], limit=1)
            self._upsert('step.tracker.work_order', company, item['id'], {
                'code': item.get('code'),
                'work_date': item.get('work_date'),
                'season': item.get('season'),
                'machine_id': machine.id if machine else False,
                'activity_id': activity.id if activity else False,
                'labor_id': labor.id if labor else False,
                'implement_id': implement.id if implement else False,
                'field_id': field.id if field else False,
                'analytic_account_id': field.analytic_account_id.id if field and field.analytic_account_id else False,
                'notes': item.get('notes'),
                'hourmeter_initial': item.get('hourmeter_initial') or 0.0,
                'hourmeter_final': item.get('hourmeter_final') or 0.0,
                'fuel_tank_start_liters': item.get('fuel_tank_start_liters') or 0.0,
                'fuel_tank_end_liters': item.get('fuel_tank_end_liters') or 0.0,
                'fuel_refill_liters': item.get('fuel_refill_liters') or 0.0,
            })
        return len(data)
