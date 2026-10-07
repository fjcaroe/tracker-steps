"""Hechos de uso: IDs de origen, período completo, cantidades y aislamiento por compañía."""
from datetime import datetime
from unittest.mock import patch

import requests
from psycopg2.errors import UniqueViolation

from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import tagged
from odoo.tools import mute_logger

from .common import FakeTracker, TrackerCase, session_item

SYNC = 'odoo.addons.step_tracker_usage.models.tracker_usage_sync'


@tagged('post_install', '-at_install')
class TestStepTrackerUsage(TrackerCase):

    def _usage(self, index=1):
        return self.env['step.tracker.usage'].sudo().search([
            ('session_uuid', '=', '00000000-0000-0000-0000-%012d' % index), ('company_id', '=', self.company.id)])

    def _upsert(self, items, work_orders=None):
        return self.usage_sync._upsert_items(self.company, items, work_orders or {})

    def test_ids_resolve_by_id_and_company_and_km_converted_once(self):
        self._upsert([session_item(1)])
        usage = self._usage(1)
        self.assertEqual(usage.machine_id, self.machine)
        self.assertEqual(usage.vehicle_id, self.vehicle)
        self.assertEqual(usage.driver_id, self.driver)
        self.assertEqual(usage.employee_id, self.employee)
        self.assertEqual(usage.analytic_account_id, self.account)
        self.assertAlmostEqual(usage.distance_km, 12.345, places=6)   # 12.345 m -> 12,345 km, una sola conversión
        self.assertTrue(usage.distance_known)
        self.assertFalse(usage.unresolved_reason)
        self.assertTrue(usage.is_closed_fact)
        self.assertAlmostEqual(usage.duration_hours, 2.0)

    def test_no_name_matching_and_reason_is_explained(self):
        """Otro conductor con el mismo nombre NO se toma: el ID 99 no existe en Odoo."""
        self.env['step.tracker.driver'].sudo().create({'tracker_id': 22, 'name': 'Operadora Uno', 'company_id': self.company.id})
        self._upsert([session_item(2, driver_id=99, cost_center_id=77, machine_id=88)])
        usage = self._usage(2)
        self.assertFalse(usage.driver_id)
        self.assertFalse(usage.cost_center_id)
        self.assertFalse(usage.machine_id)
        self.assertIn('Máquina sin registro en Odoo', usage.unresolved_reason)
        self.assertIn('Conductor no identificado', usage.unresolved_reason)
        self.assertIn('Sesión sin centro de costo', usage.unresolved_reason)

    def test_unlinked_master_data_is_reported_not_guessed(self):
        self.machine.vehicle_id = False
        self.driver.employee_id = False
        self.center.analytic_account_id = False
        self._upsert([session_item(3)])
        usage = self._usage(3)
        self.assertFalse(usage.vehicle_id)
        self.assertFalse(usage.employee_id)
        self.assertIn('Máquina sin vehículo Odoo asociado', usage.unresolved_reason)
        self.assertIn('Conductor sin empleado Odoo asociado', usage.unresolved_reason)
        self.assertIn('Centro de costo sin cuenta analítica vinculada', usage.unresolved_reason)

    def test_unknown_distance_and_open_session_are_not_valid_facts(self):
        self._upsert([session_item(4, total_distance_m=None, ended_at=None, status='open')])
        usage = self._usage(4)
        self.assertFalse(usage.distance_known)
        self.assertEqual(usage.distance_km, 0.0)
        self.assertFalse(usage.is_closed_fact)
        self.assertEqual(usage.duration_hours, 0.0)
        self.assertEqual(len(usage._data_issues()), 2)

    def test_two_hour_session_without_hourmeter_invents_nothing(self):
        self._upsert([session_item(5)], work_orders={})
        usage = self._usage(5)
        self.assertAlmostEqual(usage.duration_hours, 2.0)
        self.assertFalse(usage.hourmeter_known)
        self.assertEqual((usage.hourmeter_initial, usage.hourmeter_final), (0.0, 0.0))

    def test_hourmeter_and_refill_only_from_the_work_order_flags(self):
        work_orders = {
            7: {'id': 7, 'code': 'P-7', 'hourmeter_initial': 100.0, 'hourmeter_final': 108.5, 'fuel_refill_liters': 40.0},
            8: {'id': 8, 'code': 'P-8', 'hourmeter_initial': None, 'hourmeter_final': None, 'fuel_refill_liters': None},
            9: {'id': 9, 'code': 'P-9', 'hourmeter_initial': 0.0, 'hourmeter_final': 0.0, 'fuel_refill_liters': 0.0},
            10: {'id': 10, 'code': 'P-10', 'hourmeter_initial': 500.0, 'hourmeter_final': 400.0},
        }
        self._upsert([session_item(10 + i, work_order_id=i) for i in (7, 8, 9, 10)], work_orders)
        by_wo = {u.work_order_tracker_id: u for u in self.env['step.tracker.usage'].sudo().search([('company_id', '=', self.company.id)])}
        self.assertTrue(by_wo[7].hourmeter_known)
        self.assertEqual((by_wo[7].hourmeter_initial, by_wo[7].hourmeter_final), (100.0, 108.5))
        self.assertTrue(by_wo[7].fuel_refill_known)
        self.assertFalse(by_wo[8].hourmeter_known)
        self.assertFalse(by_wo[8].fuel_refill_known)
        self.assertFalse(by_wo[9].hourmeter_known, '0/0 no es una lectura real')
        self.assertTrue(by_wo[9].fuel_refill_known, 'Una recarga de 0 L informada explícitamente sí es un dato')
        self.assertFalse(by_wo[10].hourmeter_known, 'Final menor que inicial es una lectura inválida')
        self.assertFalse(by_wo[10].fuel_refill_known)

    def test_estimated_fuel_is_kept_separate_and_labelled(self):
        self._upsert([session_item(6)])
        usage = self._usage(6)
        self.assertEqual(usage.estimated_fuel_liters, 14.5)
        self.assertFalse(usage.fuel_refill_known)
        self.assertIn('No es combustible comprado', usage._fields['estimated_fuel_liters'].help)

    def test_resync_is_idempotent_and_db_constraint_holds(self):
        for _i in range(3):
            self._upsert([session_item(7)])
        self.assertEqual(len(self._usage(7)), 1)
        with self.assertRaises(UniqueViolation), self.env.cr.savepoint(), mute_logger('odoo.sql_db'):
            self.env['step.tracker.usage'].sudo().create({
                'session_uuid': '00000000-0000-0000-0000-000000000007', 'company_id': self.company.id,
                'started_at': datetime(2026, 9, 10, 12)})

    def test_work_order_session_count_flags_shared_reading(self):
        work_orders = {5: {'id': 5, 'code': 'P-5', 'hourmeter_initial': 10.0, 'hourmeter_final': 18.0}}
        self._upsert([session_item(20, work_order_id=5), session_item(21, work_order_id=5)], work_orders)
        self.assertEqual(self._usage(20).work_order_session_count, 2)

    # ---- período completo --------------------------------------------------
    def test_more_than_500_sessions_are_all_retrieved(self):
        tracker = FakeTracker(sessions=[session_item(1000 + i) for i in range(1234)], page_size=500)
        with self.token_patch(), tracker.patch():
            result = self.usage_sync.sync_period(self.company, datetime(2026, 9, 1), datetime(2026, 10, 1), machine_tracker_id=11)
        self.assertEqual(result['fetched'], 1234)
        self.assertTrue(result['complete'])
        self.assertEqual(result['source'], 'period')
        self.assertEqual(sum(1 for url, _p in tracker.calls if url.endswith('/sessions/period')), 3)
        first = next(p for url, p in tracker.calls if url.endswith('/sessions/period'))
        self.assertEqual(first['from'], '2026-09-01T00:00:00Z')
        self.assertEqual(first['machine_id'], 11)
        self.assertEqual(self.env['step.tracker.usage'].sudo().search_count([('company_id', '=', self.company.id)]), 1234)

    def test_period_sync_creates_masters_and_keeps_explicit_links(self):
        tracker = FakeTracker(sessions=[session_item(1), session_item(2, machine_id=12)])
        with self.token_patch(), tracker.patch():
            self.usage_sync.sync_period(self.company, datetime(2026, 9, 1), datetime(2026, 10, 1))
        camioneta = self.env['step.tracker.machine'].sudo().search([('tracker_id', '=', 12), ('company_id', '=', self.company.id)])
        self.assertTrue(camioneta, 'La máquina nueva se sincroniza sola')
        self.assertFalse(camioneta.vehicle_id)
        self.assertEqual(self.machine.vehicle_id, self.vehicle, 'El vínculo explícito existente no se pisa')
        self.assertEqual(self.center.analytic_account_id, self.account)
        self.assertIn('Máquina sin vehículo Odoo asociado', self._usage(2).unresolved_reason)

    def test_truncated_period_is_never_reported_complete(self):
        tracker = FakeTracker(sessions=[session_item(3000 + i) for i in range(10)], page_size=2)
        with self.token_patch(), tracker.patch(), patch('%s.PERIOD_MAX_PAGES' % SYNC, 2):
            result = self.usage_sync.sync_period(self.company, datetime(2026, 9, 1), datetime(2026, 10, 1))
        self.assertFalse(result['complete'])
        self.assertEqual(result['fetched'], 4)
        self.assertTrue(result['warnings'])

    def test_old_api_without_period_contract_warns_incomplete(self):
        tracker = FakeTracker(sessions=[session_item(1), session_item(2)], period_contract=False)
        with self.token_patch(), tracker.patch():
            result = self.usage_sync.sync_period(self.company, datetime(2026, 9, 1), datetime(2026, 10, 1))
        self.assertEqual(result['source'], 'search')
        self.assertFalse(result['complete'])
        self.assertIn('INICIAN', result['warnings'][0])
        self.assertEqual(result['fetched'], 2)

    def test_tracker_down_gives_clear_retryable_error_and_changes_nothing(self):
        before = self.env['step.tracker.usage'].sudo().search_count([('company_id', '=', self.company.id)])
        tracker = FakeTracker(fail=requests.ConnectTimeout('timeout'))
        with self.token_patch(), tracker.patch():
            with self.assertRaisesRegex(UserError, 'No se modificó ningún documento'):
                self.usage_sync.sync_period(self.company, datetime(2026, 9, 1), datetime(2026, 10, 1))
        self.assertEqual(self.env['step.tracker.usage'].sudo().search_count([('company_id', '=', self.company.id)]), before)

    def test_period_domain_includes_crossing_sessions_and_excludes_outside(self):
        self._upsert([
            session_item(30, started_at='2026-09-09T22:00:00Z', ended_at='2026-09-10T01:00:00Z'),   # cruza el inicio
            session_item(31, started_at='2026-09-09T01:00:00Z', ended_at='2026-09-09T03:00:00Z'),   # antes
            session_item(32, started_at='2026-09-11T05:00:00Z', ended_at='2026-09-11T06:00:00Z'),   # después
            session_item(33, started_at='2026-09-10T20:00:00Z', ended_at=None, status='open', total_distance_m=None),
        ])
        domain = self.env['step.tracker.usage']._period_domain(datetime(2026, 9, 10), datetime(2026, 9, 11))
        found = self.env['step.tracker.usage'].sudo().search(domain + [('company_id', '=', self.company.id)])
        self.assertEqual(sorted(found.mapped('session_uuid')), [
            '00000000-0000-0000-0000-000000000030', '00000000-0000-0000-0000-000000000033'])

    # ---- aislamiento por compañía -----------------------------------------------
    def test_company_constraints_on_explicit_links(self):
        foreign_account = self.account.copy({'name': 'Otra', 'company_id': self.other_company.id})
        with self.assertRaises(ValidationError):
            self.center.analytic_account_id = foreign_account
        foreign_machine = self.env['step.tracker.machine'].sudo().create({
            'tracker_id': 91, 'name': 'Otra', 'company_id': self.other_company.id})
        with self.assertRaises(UserError):   # check_company del ORM
            self.env['step.tracker.usage'].sudo().create({
                'session_uuid': 'x-cross', 'company_id': self.company.id, 'started_at': datetime(2026, 9, 10),
                'machine_id': foreign_machine.id})

    def test_record_rules_hide_other_company_data_even_on_legacy_mirrors(self):
        self._upsert([session_item(40)])
        legacy_session = self.env['step.tracker.session'].sudo().create({
            'tracker_id': 'legacy-1', 'started_at': datetime(2026, 9, 10), 'company_id': self.company.id})
        user_b = self.env['res.users'].create({
            'name': 'Usuario B', 'login': 'trk_qa_user_b', 'company_id': self.other_company.id,
            'company_ids': [(6, 0, [self.other_company.id])],
            'groups_id': [(6, 0, [self.env.ref('base.group_user').id])],
        })
        usage = self._usage(40)
        self.assertFalse(self.env['step.tracker.usage'].with_user(user_b).search([('id', '=', usage.id)]))
        for record in (usage, legacy_session, self.machine, self.driver, self.center):
            with self.assertRaises(AccessError, msg=record._name):
                record.with_user(user_b).read(['display_name'])
