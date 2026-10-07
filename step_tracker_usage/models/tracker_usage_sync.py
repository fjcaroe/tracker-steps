"""Sincronización por período de los hechos de uso.

Reutiliza la conexión, el login y el token de ``step.tracker.sync`` (definido por
``step_hr`` y/o ``step_tracker_odoo``: ambas versiones exponen la misma interfaz), pero no
modifica ni reemplaza ese servicio.
"""
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None

DEFAULT_TIMEOUT = 20
PERIOD_PAGE_SIZE = 500
PERIOD_MAX_PAGES = 200
SEARCH_FALLBACK_LIMIT = 5000


class StepTrackerUsageSync(models.AbstractModel):
    _name = 'step.tracker.usage.sync'
    _description = 'Sincronización de uso de vehículos desde Web Tracker'

    @api.model
    def _legacy(self):
        return self.env['step.tracker.sync']

    @staticmethod
    def _api_datetime(value):
        """datetime naive en UTC (convención de Odoo) -> ISO 8601 con Z para la API."""
        return value.strftime('%Y-%m-%dT%H:%M:%SZ')

    @api.model
    def _advertised_capabilities(self, base_url):
        resp = requests.get(f'{base_url}/health/capabilities', timeout=DEFAULT_TIMEOUT)
        resp.raise_for_status()
        return set(resp.json().get('capabilities') or [])

    # ------------------------------------------------------------------
    # Maestros que el hecho de uso necesita resolver
    # ------------------------------------------------------------------
    @api.model
    def _sync_cost_centers(self, company, base_url):
        data = self._legacy()._get_json(company, base_url, '/cost_centers')
        CostCenter = self.env['step.tracker.cost_center'].sudo()
        now = fields.Datetime.now()
        for item in data:
            values = {
                'name': item.get('name') or _('Centro de costo %s') % item['id'],
                'external_id': item.get('external_id'),
                'last_sync': now,
            }
            # analytic_account_id NO se toca: es el vínculo explícito que mantiene el usuario.
            record = CostCenter.search([('tracker_id', '=', item['id']), ('company_id', '=', company.id)], limit=1)
            if record:
                record.write(values)
            else:
                CostCenter.create(dict(values, tracker_id=item['id'], company_id=company.id))
        return len(data)

    @api.model
    def _work_order_index(self, company, base_url):
        data = self._legacy()._get_json(company, base_url, '/work_orders')
        return {item['id']: item for item in data}

    # ------------------------------------------------------------------
    # Escritura idempotente de hechos
    # ------------------------------------------------------------------
    @api.model
    def _upsert_items(self, company, items, work_orders):
        Usage = self.env['step.tracker.usage'].sudo()
        Machine = self.env['step.tracker.machine'].sudo()
        Driver = self.env['step.tracker.driver'].sudo()
        CostCenter = self.env['step.tracker.cost_center'].sudo()
        now = fields.Datetime.now()
        parse = self._legacy()._parse_dt
        for item in items:
            machine = Machine.search([('tracker_id', '=', item.get('machine_id')), ('company_id', '=', company.id)], limit=1)
            driver = Driver.search([('tracker_id', '=', item.get('driver_id')), ('company_id', '=', company.id)],
                                   limit=1) if item.get('driver_id') else Driver
            center = CostCenter.search([('tracker_id', '=', item.get('cost_center_id')), ('company_id', '=', company.id)],
                                       limit=1) if item.get('cost_center_id') else CostCenter
            distance_m = item.get('total_distance_m')
            wo = work_orders.get(item.get('work_order_id')) or {}
            hour_i, hour_f = wo.get('hourmeter_initial'), wo.get('hourmeter_final')
            values = {
                'machine_id': machine.id or False,
                'driver_id': driver.id or False,
                'cost_center_id': center.id or False,
                'started_at': parse(item.get('started_at')),
                'ended_at': parse(item.get('ended_at')),
                'status': item.get('status') or 'open',
                'points_count': item.get('points_count') or 0,
                # Distancia desconocida (None) no es una distancia de cero.
                'distance_known': distance_m is not None,
                'distance_km': (distance_m or 0) / 1000.0,
                'estimated_fuel_liters': item.get('estimated_fuel_liters') or 0.0,
                'work_order_tracker_id': item.get('work_order_id') or 0,
                'work_order_code': wo.get('code') or False,
                'hourmeter_initial': hour_i or 0.0,
                'hourmeter_final': hour_f or 0.0,
                # Una lectura solo es real si Tracker entregó ambas, son coherentes y no son 0/0.
                'hourmeter_known': bool(
                    hour_i is not None and hour_f is not None and hour_f >= hour_i and hour_f > 0),
                'fuel_refill_liters': wo.get('fuel_refill_liters') or 0.0,
                'fuel_refill_known': wo.get('fuel_refill_liters') is not None,
                'synced_at': now,
            }
            uuid = str(item['id'])
            record = Usage.search([('session_uuid', '=', uuid), ('company_id', '=', company.id)], limit=1)
            if record:
                record.write(values)
            else:
                Usage.create(dict(values, session_uuid=uuid, company_id=company.id))
        return len(items)

    # ------------------------------------------------------------------
    # Punto de entrada
    # ------------------------------------------------------------------
    @api.model
    def sync_period(self, company, date_from, date_to, machine_tracker_id=None):
        """Trae de Tracker TODAS las sesiones que tocan [date_from, date_to) (UTC naive).

        Devuelve ``{'complete', 'fetched', 'source', 'warnings'}``. ``complete`` solo es
        True cuando se demostró que no hubo truncamiento: nunca se presenta como completo
        un resultado cortado por límite de página o de número de páginas. Un fallo de red
        o de API se informa sin modificar documentos y se puede reintentar (upsert idempotente).
        """
        if requests is None:
            raise UserError(_('El paquete Python "requests" no está disponible en este servidor de Odoo.'))
        company, base_url = self._legacy()._get_company_config(company)
        result = {'complete': False, 'fetched': 0, 'source': '', 'warnings': []}
        try:
            capabilities = self._advertised_capabilities(base_url)
            self._legacy()._sync_machines(company, base_url)
            self._legacy()._sync_drivers(company, base_url)
            self._sync_cost_centers(company, base_url)
            work_orders = self._work_order_index(company, base_url)
            params = {'from': self._api_datetime(date_from), 'to': self._api_datetime(date_to)}
            if machine_tracker_id:
                params['machine_id'] = machine_tracker_id
            if 'sessions_period_v1' in capabilities:
                result['source'] = 'period'
                page_cursor, pages = None, 0
                while pages < PERIOD_MAX_PAGES:
                    page_params = dict(params, limit=PERIOD_PAGE_SIZE)
                    if page_cursor:
                        page_params['cursor'] = page_cursor
                    page = self._legacy()._get_json(company, base_url, '/sessions/period', params=page_params)
                    result['fetched'] += self._upsert_items(company, page['items'], work_orders)
                    pages += 1
                    page_cursor = page.get('next_cursor')
                    if not page_cursor:
                        result['complete'] = bool(page.get('complete'))
                        break
                else:
                    result['warnings'].append(_(
                        'Se alcanzó el máximo de páginas del período; los resultados pueden estar incompletos.'))
            else:
                # API anterior: solo filtra por INICIO y no pagina. Se informa su límite.
                result['source'] = 'search'
                items = self._legacy()._get_json(company, base_url, '/sessions/search', params=dict(
                    params, limit=SEARCH_FALLBACK_LIMIT))
                result['fetched'] += self._upsert_items(company, items, work_orders)
                result['warnings'].append(_(
                    'La API de Tracker no publica el contrato por período: solo se consultaron las sesiones que '
                    'INICIAN dentro del rango (máx. %(limit)s). Las que empezaron antes y cruzan el inicio del '
                    'rango pueden faltar; no se da el período por completo.'
                ) % {'limit': SEARCH_FALLBACK_LIMIT})
        except requests.RequestException as exc:
            _logger.warning('step.tracker.usage.sync: falló la consulta a Tracker (%s)', type(exc).__name__)
            raise UserError(_(
                'No se pudo consultar Web Tracker (%(error)s). No se modificó ningún documento; '
                'puede reintentar más tarde.'
            ) % {'error': type(exc).__name__}) from exc
        return result
