"""Utilidades compartidas por las pruebas de los módulos puente de Tracker."""
from unittest.mock import patch

import requests

from odoo.tests.common import TransactionCase


class FakeResponse:
    def __init__(self, payload, status=200):
        self._payload, self.status_code = payload, status

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError('error %s' % self.status_code)


def session_item(index, **overrides):
    """Sesión tal como la entrega GET /sessions/period (IDs de origen incluidos)."""
    item = {
        'id': '00000000-0000-0000-0000-%012d' % index, 'machine_id': 11, 'driver_id': 21,
        'cost_center_id': 31, 'started_at': '2026-09-10T12:00:00Z', 'ended_at': '2026-09-10T14:00:00Z',
        'status': 'closed', 'points_count': 10, 'total_distance_m': 12345.0, 'avg_speed_kmh': 6.2,
        'estimated_fuel_liters': 14.5, 'work_order_id': None,
    }
    item.update(overrides)
    return item


class FakeTracker:
    """API de Tracker simulada: maestros, partes y sesiones por período con cursor."""

    def __init__(self, sessions=None, work_orders=None, page_size=500, period_contract=True, fail=None):
        self.sessions = sessions or []
        self.work_orders = work_orders or []
        self.page_size = page_size
        self.period_contract = period_contract
        self.fail = fail
        self.calls = []

    def get(self, url, headers=None, params=None, timeout=None):
        self.calls.append((url, dict(params or {})))
        if self.fail:
            raise self.fail
        path = url.split('tracker.test', 1)[1]
        params = params or {}
        if path == '/health/capabilities':
            caps = ['odoo_sync_v1'] + (['sessions_period_v1'] if self.period_contract else [])
            return FakeResponse({'capabilities': caps})
        if path == '/machines':
            return FakeResponse([{'id': 11, 'name': 'Tractor QA', 'plate': 'QA-0001', 'is_active': True},
                                 {'id': 12, 'name': 'Camioneta QA', 'plate': 'QA-0002', 'is_active': True}])
        if path == '/drivers':
            return FakeResponse([{'id': 21, 'name': 'Operadora Uno', 'is_active': True}])
        if path == '/cost_centers':
            return FakeResponse([{'id': 31, 'name': 'Cuartel QA', 'external_id': 'CQ'}])
        if path == '/work_orders':
            return FakeResponse(self.work_orders)
        if path == '/sessions/period':
            machine = params.get('machine_id')
            rows = [s for s in self.sessions if not machine or s['machine_id'] == int(machine)]
            start = int(params.get('cursor') or 0)
            page = rows[start:start + self.page_size]
            nxt = start + self.page_size
            more = nxt < len(rows)
            return FakeResponse({'items': page, 'next_cursor': str(nxt) if more else None,
                                 'complete': not more, 'total': len(rows)})
        if path == '/sessions/search':
            return FakeResponse(self.sessions[:5000])
        raise AssertionError('Ruta no simulada: %s' % path)

    def patch(self):
        return patch('requests.get', side_effect=self.get)


class TrackerCase(TransactionCase):
    """Compañía con Tracker configurado, vehículo, empleado, cuenta analítica y vínculos explícitos."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({'name': 'Tracker QA A', 'step_tracker_base_url': 'http://tracker.test'})
        cls.other_company = cls.env['res.company'].create({'name': 'Tracker QA B', 'step_tracker_base_url': 'http://tracker.test'})
        cls.env.user.company_ids |= cls.company | cls.other_company
        cls.legacy = cls.env['step.tracker.sync'].with_company(cls.company)
        cls.usage_sync = cls.env['step.tracker.usage.sync'].with_company(cls.company)
        cls.employee = cls.env['hr.employee'].create({'name': 'Operadora Uno', 'company_id': cls.company.id})
        brand = cls.env['fleet.vehicle.model.brand'].create({'name': 'Marca QA'})
        cls.fleet_model = cls.env['fleet.vehicle.model'].create({'name': 'Modelo QA', 'brand_id': brand.id})
        cls.vehicle = cls._vehicle('QA-0001', cls.company)
        cls.plan = cls.env['account.analytic.plan'].create({'name': 'Plan QA'})
        cls.account = cls.env['account.analytic.account'].create({
            'name': 'Cuartel QA', 'plan_id': cls.plan.id, 'company_id': cls.company.id})
        cls.machine = cls.env['step.tracker.machine'].sudo().create({
            'tracker_id': 11, 'name': 'Tractor QA', 'company_id': cls.company.id, 'vehicle_id': cls.vehicle.id})
        cls.driver = cls.env['step.tracker.driver'].sudo().create({
            'tracker_id': 21, 'name': 'Operadora Uno', 'company_id': cls.company.id, 'employee_id': cls.employee.id})
        cls.center = cls.env['step.tracker.cost_center'].sudo().create({
            'tracker_id': 31, 'name': 'Cuartel QA', 'company_id': cls.company.id, 'analytic_account_id': cls.account.id})

    @classmethod
    def _vehicle(cls, plate, company):
        return cls.env['fleet.vehicle'].create({
            'model_id': cls.fleet_model.id, 'license_plate': plate, 'company_id': company.id})

    def token_patch(self):
        return patch.object(type(self.legacy), '_get_token', return_value='tok')
