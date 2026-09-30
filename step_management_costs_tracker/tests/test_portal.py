"""Entrega B: vínculo activo ↔ vehículo y endpoint de costos del portal."""
from datetime import date
from unittest.mock import MagicMock, patch

from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import HttpCase, tagged

from .common import CostCase

ASSET = '11111111-2222-4333-8444-555555555555'
FOREIGN_ASSET = 'aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee'
ROUTE = '/steps_tracker/costs/assets/%s'


def gps_response(payload, status=200):
    response = MagicMock()
    response.status_code = status
    response.json.return_value = payload
    return response


@tagged('post_install', '-at_install')
class TestAssetLink(CostCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.manager = cls.env['res.users'].create({
            'name': 'Admin Tracker QA', 'login': 'trk_link_manager', 'company_id': cls.company.id,
            'company_ids': [(6, 0, [cls.company.id])],
            'groups_id': [(6, 0, [cls.env.ref('base.group_user').id, cls.env.ref('step_tracker_portal.group_tracker_manager').id])]})
        cls.viewer = cls.env['res.users'].create({
            'name': 'Visor Tracker QA', 'login': 'trk_link_viewer', 'company_id': cls.company.id,
            'company_ids': [(6, 0, [cls.company.id])],
            'groups_id': [(6, 0, [cls.env.ref('base.group_user').id, cls.env.ref('step_tracker_portal.group_tracker_viewer').id])]})
        cls.env['ir.config_parameter'].sudo().set_param('step_tracker_portal.bridge_key', 'clave-de-prueba')
        cls.Link = cls.env['step.tracker.asset.link']

    def _links(self, user=None):
        return (self.Link.with_user(user) if user else self.Link).with_company(self.company)

    def test_manual_link_is_verified_against_tracker_with_the_company_identity(self):
        calls = []

        def fake(self_, company, path, params=None):
            calls.append((company.id, path))
            return gps_response({'asset_id': ASSET, 'name': 'Camioneta portal', 'plate': 'ZZ-1'})

        with patch.object(type(self.Link), '_gps_get', fake):
            link = self._links(self.manager).create({'asset_id': ASSET, 'vehicle_id': self.vehicle.id, 'company_id': self.company.id})
        self.assertEqual(calls, [(self.company.id, 'assets/%s' % ASSET)])
        self.assertEqual((link.asset_name, link.asset_plate, link.source), ('Camioneta portal', 'ZZ-1', 'manual'))
        self.assertEqual(self.vehicle.tracker_asset_id, ASSET)

    def test_foreign_or_unknown_asset_cannot_be_linked(self):
        with patch.object(type(self.Link), '_gps_get', lambda *a, **k: gps_response({'detail': 'nope'}, 404)):
            with self.assertRaisesRegex(ValidationError, 'no existe en Tracker'):
                self._links(self.manager).create({'asset_id': FOREIGN_ASSET, 'vehicle_id': self.vehicle.id, 'company_id': self.company.id})

    def test_only_tracker_managers_link_assets(self):
        with patch.object(type(self.Link), '_gps_get', lambda *a, **k: gps_response({'name': 'x', 'plate': None})):
            with self.assertRaises(AccessError):
                self._links(self.viewer).create({'asset_id': ASSET, 'vehicle_id': self.vehicle.id, 'company_id': self.company.id})
        with self.assertRaises(AccessError):
            self._links(self.viewer).sync_from_tracker()

    def test_one_active_link_per_vehicle_and_per_asset_with_history(self):
        with patch.object(type(self.Link), '_gps_get', lambda *a, **k: gps_response({'name': 'x', 'plate': None})):
            link = self._links(self.manager).create({'asset_id': ASSET, 'vehicle_id': self.vehicle.id, 'company_id': self.company.id})
            with self.assertRaises(Exception), self.env.cr.savepoint():
                self._links(self.manager).create({'asset_id': FOREIGN_ASSET, 'vehicle_id': self.vehicle.id, 'company_id': self.company.id})
            with self.assertRaises(Exception), self.env.cr.savepoint():
                self._links(self.manager).create({'asset_id': ASSET, 'vehicle_id': self.other_vehicle.id, 'company_id': self.company.id})
            link.with_user(self.manager).active = False
            self.env.flush_all()
            replacement = self._links(self.manager).create({'asset_id': FOREIGN_ASSET, 'vehicle_id': self.vehicle.id, 'company_id': self.company.id})
        self.assertEqual(self.vehicle.tracker_asset_id, FOREIGN_ASSET)
        self.assertTrue(replacement.active and not link.active)
        with self.assertRaisesRegex(UserError, 'no se cambia'):
            replacement.with_user(self.manager).asset_id = ASSET

    def test_link_cannot_cross_companies(self):
        other = self.env['res.company'].create({'name': 'Otra empresa QA'})
        foreign_vehicle = self.env['fleet.vehicle'].create({
            'model_id': self.vehicle.model_id.id, 'license_plate': 'XX-0001', 'company_id': other.id})
        with patch.object(type(self.Link), '_gps_get', lambda *a, **k: gps_response({'name': 'x', 'plate': None})):
            with self.assertRaises(Exception):
                self._links(self.manager).create({'asset_id': ASSET, 'vehicle_id': foreign_vehicle.id, 'company_id': self.company.id})

    def test_sync_from_tracker_links_only_odoo_vehicles_of_the_company(self):
        other = self.env['res.company'].create({'name': 'Otra empresa QA 2'})
        foreign_vehicle = self.env['fleet.vehicle'].create({
            'model_id': self.vehicle.model_id.id, 'license_plate': 'XX-0002', 'company_id': other.id})
        pages = {
            '': {'items': [
                {'asset_id': 'a-1', 'source_id': 'odoo:fleet.vehicle:%s' % self.vehicle.id, 'name': 'Tractor', 'plate': 'CQ-0001'},
                {'asset_id': 'a-2', 'source_id': 'manual:abc', 'name': 'Manual', 'plate': None},
                {'asset_id': 'a-3', 'source_id': 'odoo:fleet.vehicle:%s' % foreign_vehicle.id, 'name': 'Ajeno', 'plate': None}],
                'next_cursor': 'a-3'},
            'a-3': {'items': [
                {'asset_id': 'a-4', 'source_id': 'odoo:fleet.vehicle:999999999', 'name': 'Borrado', 'plate': None},
                {'asset_id': 'a-5', 'source_id': 'odoo:fleet.vehicle:oops', 'name': 'Raro', 'plate': None},
                {'asset_id': 'a-6', 'source_id': 'odoo:fleet.vehicle:%s' % self.other_vehicle.id, 'name': 'Otro', 'plate': None}],
                'next_cursor': None},
        }
        seen = []

        def fake(self_, company, path, params=None):
            seen.append(params['after'])
            return gps_response(pages[params['after']])

        with patch.object(type(self.Link), '_gps_get', fake):
            result = self._links(self.manager).sync_from_tracker(self.company)
            again = self._links(self.manager).sync_from_tracker(self.company)
        self.assertEqual(seen, ['', 'a-3', '', 'a-3'])
        self.assertEqual(result, {'created': 2, 'existing': 0, 'conflicts': 0, 'skipped': 4})
        self.assertEqual(again, {'created': 0, 'existing': 2, 'conflicts': 0, 'skipped': 4}, 'La sincronización es idempotente')
        self.assertEqual(self.vehicle.tracker_asset_id, 'a-1')
        self.assertEqual(self.Link.search([('asset_id', '=', 'a-1')]).source, 'odoo_import')
        self.assertFalse(self.Link.search([('asset_id', 'in', ['a-2', 'a-3'])]), 'Ni manuales ni de otra empresa')

    def test_sync_never_moves_an_existing_link(self):
        self.Link.with_context(step_tracker_skip_remote=True, step_tracker_link_sync=True).sudo().create({
            'asset_id': 'keep-1', 'vehicle_id': self.vehicle.id, 'company_id': self.company.id, 'source': 'odoo_import'})
        page = {'items': [{'asset_id': 'other-asset', 'source_id': 'odoo:fleet.vehicle:%s' % self.vehicle.id, 'name': 'Tractor', 'plate': None}],
                'next_cursor': None}
        with patch.object(type(self.Link), '_gps_get', lambda *a, **k: gps_response(page)):
            result = self._links(self.manager).sync_from_tracker(self.company)
        self.assertEqual((result['created'], result['conflicts']), (0, 1))
        self.assertEqual(self.vehicle.tracker_asset_id, 'keep-1')

    def test_link_records_are_company_scoped(self):
        self.Link.with_context(step_tracker_skip_remote=True, step_tracker_link_sync=True).sudo().create({
            'asset_id': 'scope-1', 'vehicle_id': self.vehicle.id, 'company_id': self.company.id, 'source': 'odoo_import'})
        other = self.env['res.company'].create({'name': 'Otra empresa QA 3'})
        user_b = self.env['res.users'].create({
            'name': 'Usuario B', 'login': 'trk_link_b', 'company_id': other.id, 'company_ids': [(6, 0, [other.id])],
            'groups_id': [(6, 0, [self.env.ref('base.group_user').id])]})
        self.assertFalse(self.Link.with_user(user_b).search([('asset_id', '=', 'scope-1')]))
        self.assertFalse(self.Link._resolve(other, 'scope-1'))


@tagged('post_install', '-at_install')
class TestCostsEndpoint(HttpCase, CostCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.other_company = env['res.company'].create({'name': 'Empresa B QA'})

        def user(login, groups, company=None, extra_companies=()):
            company = company or cls.company
            ids = [env.ref(g).id for g in groups]
            return env['res.users'].create({
                'name': login, 'login': login, 'password': login, 'company_id': company.id,
                'company_ids': [(6, 0, [company.id, *[c.id for c in extra_companies]])], 'groups_id': [(6, 0, ids)]})

        finance = ['base.group_user', 'step_tracker_portal.group_tracker_viewer', 'hr_expense.group_hr_expense_manager',
                   'account.group_account_readonly', 'step_management_costs.group_management_readonly']
        cls.finance_user = user('trk_fin', finance)
        cls.operator_user = user('trk_op', ['base.group_user', 'step_tracker_portal.group_tracker_operator'])
        cls.employee_viewer = user('trk_emp', ['base.group_user', 'step_tracker_portal.group_tracker_viewer'])
        cls.employee.user_id = cls.employee_viewer      # dueño de los gastos de prueba: los ve como empleado, no como aprobador
        cls.team_approver = user('trk_team', ['base.group_user', 'step_tracker_portal.group_tracker_viewer',
                                              'hr_expense.group_hr_expense_team_approver'])
        cls.expenses_only = user('trk_expall', ['base.group_user', 'step_tracker_portal.group_tracker_viewer',
                                                'hr_expense.group_hr_expense_user'])
        cls.accounting_only = user('trk_acc', ['base.group_user', 'step_tracker_portal.group_tracker_viewer',
                                               'account.group_account_readonly'])
        cls.plain_user = user('trk_plain', ['base.group_user'])
        cls.other_user = user('trk_b', finance, company=cls.other_company)
        env['ir.config_parameter'].sudo().set_param('step_tracker_portal.bridge_key', 'clave-de-prueba')
        cls.Link = env['step.tracker.asset.link']
        Link = cls.Link.with_context(step_tracker_skip_remote=True, step_tracker_link_sync=True).sudo()
        Link.create({'asset_id': ASSET, 'vehicle_id': cls.vehicle.id, 'company_id': cls.company.id, 'source': 'odoo_import'})
        foreign_vehicle = env['fleet.vehicle'].create({
            'model_id': cls.vehicle.model_id.id, 'license_plate': 'BB-0001', 'company_id': cls.other_company.id})
        Link.create({'asset_id': FOREIGN_ASSET, 'vehicle_id': foreign_vehicle.id, 'company_id': cls.other_company.id,
                     'source': 'odoo_import'})
        # datos financieros del vehículo de la compañía A
        posted = cls.expense(100000, state='post', name='Combustible QA secreto')
        cls.post_expense_move(posted, 100000)
        cls.expense(25000, name='Peaje QA secreto')
        cls.usage(1)

    def _get(self, login, asset=ASSET, query='from=2026-09-01&to=2026-09-30', cookies=None):
        self.authenticate(login, login)
        if cookies:
            for key, value in cookies.items():
                self.opener.cookies.set(key, value)
        return self.url_open('%s?%s' % (ROUTE % asset, query))

    def test_finance_user_gets_costs_with_their_permissions(self):
        response = self._get('trk_fin')
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertTrue(data['linked'])
        self.assertEqual(data['vehicle']['plate'], 'CQ-0001')
        self.assertEqual(data['real']['amount'], 100000.0)
        self.assertEqual(data['pending']['amount'], 25000.0)
        self.assertEqual(data['quantities']['km']['value'], 12.345)
        self.assertEqual(data['indicators']['cost_per_km']['status'], 'incomplete')   # hay un gasto pendiente
        self.assertIn('Cache-Control', response.headers)
        self.assertEqual(response.headers['Cache-Control'], 'no-store')
        self.assertIn('/odoo/action-fleet.fleet_vehicle_action/%s' % self.vehicle.id, data['links']['vehicle'])
        self.assertTrue(data['links']['expenses'])
        names = [doc['name'] for doc in data['documents']]
        self.assertIn('Combustible QA secreto', names)

    def test_map_operator_without_expenses_or_costs_access_gets_no_amounts(self):
        """El rol de Tracker no concede acceso financiero, aunque se llame al endpoint directamente."""
        response = self._get('trk_op')
        self.assertEqual(response.status_code, 403)
        body = response.text
        for secret in ('secreto', '100000', '25000', 'amount', 'Combustible'):
            self.assertNotIn(secret, body)

    def test_employee_with_own_vehicle_expenses_gets_no_aggregate_costs(self):
        """Un empleado ve sus propios gastos en Odoo, pero con eso no se puede entregar el total de un vehículo."""
        own = self.env['hr.expense'].search([('name', '=', 'Peaje QA secreto')])
        self.assertTrue(own.with_user(self.employee_viewer).has_access('read'), 'El empleado sí ve su gasto en Odoo')
        response = self._get('trk_emp')
        self.assertEqual(response.status_code, 403)
        self.assertNotIn('Peaje', response.text)
        self.assertNotIn('25000', response.text)

    def test_team_approver_with_partial_visibility_gets_no_totals(self):
        """Un aprobador de equipo ve gastos y apuntes solo en parte: no se le entregan totales que parezcan completos."""
        response = self._get('trk_team')
        self.assertEqual(response.status_code, 403)
        self.assertNotIn('100000', response.text)

    def test_expenses_user_without_accounting_sees_pending_but_real_is_unavailable(self):
        data = self._get('trk_expall').json()
        self.assertTrue(data['access']['expenses'])
        self.assertFalse(data['access']['accounting'])
        self.assertFalse(data['real']['available'])
        self.assertIsNone(data['real']['amount'])
        self.assertEqual(data['pending']['amount'], 25000.0)
        self.assertIn('Sin permiso de lectura contable', data['real']['reason'])
        km = data['indicators']['cost_per_km']
        self.assertEqual((km['status'], km['value'], km['partial']), ('unavailable', None, None))

    def test_accounting_user_without_expenses_cannot_attribute_costs_to_a_vehicle(self):
        """La atribución pasa por los gastos: sin verlos todos, un cero sería engañoso y se informa no disponible."""
        data = self._get('trk_acc').json()
        self.assertTrue(data['access']['accounting'])
        self.assertFalse(data['access']['expenses'])
        self.assertFalse(data['real']['available'])
        self.assertIsNone(data['real']['amount'])
        self.assertIn('todos los gastos', data['real']['reason'])
        self.assertFalse(data['pending']['available'])
        self.assertEqual(data['documents'], [], 'Sin visibilidad de gastos no se listan documentos')
        self.assertEqual(data['indicators']['cost_per_km']['status'], 'unavailable')

    def test_user_without_any_tracker_role_is_rejected(self):
        self.assertEqual(self._get('trk_plain').status_code, 403)

    def test_manipulated_or_foreign_asset_id_is_rejected_without_data(self):
        with patch.object(type(self.Link), '_gps_get', lambda *a, **k: gps_response({'detail': 'no'}, 404)):
            response = self._get('trk_fin', asset=FOREIGN_ASSET)
        self.assertEqual(response.status_code, 404)
        self.assertNotIn('BB-0001', response.text)
        # y el usuario de la otra compañía no ve el activo de la compañía A
        with patch.object(type(self.Link), '_gps_get', lambda *a, **k: gps_response({'detail': 'no'}, 404)):
            response = self._get('trk_b', asset=ASSET)
        self.assertEqual(response.status_code, 404)
        self.assertNotIn('CQ-0001', response.text)
        self.assertNotIn('secreto', response.text)
        self.assertEqual(self._get('trk_fin', asset='no-es-un-id!').status_code, 400)   # formato inválido
        self.assertEqual(self._get('trk_fin', asset='zz').status_code, 400)

    def test_company_cookie_is_a_selector_never_authority(self):
        response = self._get('trk_fin', cookies={'cids': str(self.other_company.id)})
        self.assertEqual(response.status_code, 403)

    def test_manual_asset_without_vehicle_is_explained_not_linked_by_name(self):
        manual = 'ffffffff-0000-4000-8000-000000000001'
        with patch.object(type(self.Link), '_gps_get', lambda *a, **k: gps_response({'asset_id': manual, 'name': 'CQ-0001 Tractor QA', 'plate': 'CQ-0001'})):
            response = self._get('trk_fin', asset=manual)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertFalse(data['linked'])
        self.assertEqual(data['reason'], 'unlinked')
        self.assertIn('No se asocia por nombre ni por patente', data['message'])
        for key in ('real', 'pending', 'documents', 'vehicle'):
            self.assertNotIn(key, data, 'Sin vínculo no se entrega ningún dato del vehículo homónimo')

    def test_tracker_api_down_while_checking_ownership_is_a_clear_503(self):
        with patch.object(type(self.Link), '_gps_get', side_effect=UserError('La API de Tracker no está disponible; vuelva a intentar.')):
            response = self._get('trk_fin', asset='ffffffff-0000-4000-8000-000000000002')
        self.assertEqual(response.status_code, 503)
        self.assertIn('vuelva a intentar', response.json()['detail'])

    def test_bad_periods_are_rejected(self):
        self.assertEqual(self._get('trk_fin', query='from=2026-09-30&to=2026-09-01').status_code, 400)
        self.assertEqual(self._get('trk_fin', query='from=2024-01-01&to=2026-09-01').status_code, 400)
        self.assertEqual(self._get('trk_fin', query='from=xx&to=2026-09-01').status_code, 400)
        self.assertEqual(self._get('trk_fin', query='hourly=hourmeter&from=2026-09-01&to=2026-09-30').json()['hourly_metric'], 'hourmeter')

    def test_anonymous_request_is_redirected_to_login(self):
        self.opener.cookies.clear()
        response = self.url_open(ROUTE % ASSET, allow_redirects=False)
        self.assertIn(response.status_code, (302, 303, 401, 403))
        self.assertNotIn('secreto', response.text)
