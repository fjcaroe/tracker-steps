"""Entrega A: asistente «Traer desde Tracker» en rendiciones de gastos."""
from datetime import date, datetime
from unittest.mock import patch

import requests

from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import tagged

from odoo.addons.step_tracker_usage.tests.common import FakeTracker, TrackerCase, session_item


@tagged('post_install', '-at_install')
class TestExpenseTrackerImport(TrackerCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company.partner_id.tz = 'America/Santiago'
        cls.employee_user = cls.env['res.users'].create({
            'name': 'Operadora Uno', 'login': 'trk_exp_op1', 'company_id': cls.company.id,
            'company_ids': [(6, 0, [cls.company.id])],
            'groups_id': [(6, 0, [cls.env.ref('base.group_user').id,
                                  cls.env.ref('step_expense_tracker.group_expense_vehicle').id])],
        })
        cls.employee.user_id = cls.employee_user
        cls.product = cls.env['product.product'].create({'name': 'Combustible QA', 'can_be_expensed': True, 'type': 'service'})
        cls.sheet = cls._new_sheet(cls.employee)

    @classmethod
    def _new_sheet(cls, employee, company=None):
        company = company or cls.company
        expense = cls.env['hr.expense'].with_company(company).create({
            'name': 'Bencina', 'employee_id': employee.id, 'product_id': cls.product.id,
            'total_amount_currency': 50000, 'company_id': company.id, 'date': date(2026, 9, 10)})
        return cls.env['hr.expense.sheet'].with_company(company).create({
            'name': 'Viaje QA', 'employee_id': employee.id, 'company_id': company.id,
            'expense_line_ids': [(6, 0, expense.ids)]})

    # ---- utilidades ------------------------------------------------------------
    def _upsert(self, items, work_orders=None):
        self.usage_sync._upsert_items(self.company, items, work_orders or {})

    def _wizard(self, sheet=None, vehicle=None, date_from=date(2026, 9, 10), date_to=date(2026, 9, 10), **extra):
        sheet = sheet or self.sheet
        values = {'sheet_id': sheet.id, 'vehicle_id': (vehicle or self.vehicle).id,
                  'date_from': date_from, 'date_to': date_to, 'use_tracker_sync': False}
        values.update(extra)
        return self.env['step.expense.tracker.import'].with_company(self.company).create(values)

    def _preview(self, **kw):
        wizard = self._wizard(**kw)
        wizard.action_preview()
        return wizard

    def _lines(self, sheet=None):
        return (sheet or self.sheet).vehicle_line_ids

    # ---- A1: vista previa sin efectos y datos correctos ------------------------------
    def test_preview_creates_nothing_and_confirm_keeps_ids_date_and_distance(self):
        self._upsert([session_item(1, started_at='2026-09-10T12:00:00Z', ended_at='2026-09-10T14:00:00Z')])
        wizard = self._preview()
        self.assertEqual(len(wizard.line_ids), 1)
        self.assertFalse(self._lines(), 'Buscar y previsualizar no crea líneas')
        preview = wizard.line_ids
        self.assertEqual(preview.local_date, date(2026, 9, 10))
        self.assertAlmostEqual(preview.distance_km, 12.345, places=6)
        self.assertTrue(preview.selected and preview.selectable)
        wizard.action_confirm()
        line = self._lines()
        self.assertEqual(len(line), 1)
        self.assertEqual(line.vehicle_id, self.vehicle)
        self.assertEqual(line.usage_id.session_uuid, '00000000-0000-0000-0000-000000000001')
        self.assertEqual(line.driver_employee_id, self.employee)
        self.assertEqual(line.analytic_account_id, self.account)
        self.assertEqual(line.date, date(2026, 9, 10))
        self.assertAlmostEqual(line.distance, 12.345, places=6)   # 12.345 m -> 12,345 km sin doble conversión
        self.assertEqual(line.source, 'tracker')
        self.assertTrue(line.imported_at)
        self.assertEqual(line.imported_by_id, self.env.user)
        self.assertFalse(line.is_modified)
        self.assertEqual(line.action_open_usage()['res_id'], line.usage_id.id)
        self.assertTrue(self.sheet.use_vehicle)

    def test_two_hour_session_without_hourmeter_invents_nothing(self):
        self._upsert([session_item(2)])
        self._preview().action_confirm()
        line = self._lines()
        self.assertAlmostEqual(line.src_duration_hours, 2.0)
        self.assertEqual((line.start_reading, line.end_reading), (0.0, 0.0))
        self.assertFalse(line.src_hourmeter_known)

    def test_real_hourmeter_is_imported_but_distance_stays_gps(self):
        wo = {7: {'id': 7, 'code': 'P-7', 'hourmeter_initial': 100.0, 'hourmeter_final': 108.5}}
        self._upsert([session_item(3, work_order_id=7)], wo)
        self._preview().action_confirm()
        line = self._lines()
        self.assertEqual((line.start_reading, line.end_reading), (100.0, 108.5))
        self.assertAlmostEqual(line.distance, 12.345, places=6, msg='Km no es la diferencia entre lecturas de horómetro')
        # editar las lecturas no debe pisar los km GPS de una línea importada
        line.start_reading = 101.0
        self.assertAlmostEqual(line.distance, 12.345, places=6)

    def test_shared_work_order_reading_is_not_duplicated_across_sessions(self):
        wo = {7: {'id': 7, 'code': 'P-7', 'hourmeter_initial': 100.0, 'hourmeter_final': 108.5, 'fuel_refill_liters': 40.0}}
        self._upsert([session_item(4, work_order_id=7), session_item(5, work_order_id=7,
                                                                     started_at='2026-09-10T16:00:00Z', ended_at='2026-09-10T17:00:00Z')], wo)
        wizard = self._preview()
        self.assertEqual(len(wizard.line_ids), 2)
        for preview in wizard.line_ids:
            self.assertFalse(preview.hourmeter_available)
            self.assertFalse(preview.refill_available)
            self.assertIn('cubre 2 sesiones', preview.issues)
        wizard.action_confirm()
        for line in self._lines():
            self.assertEqual((line.start_reading, line.end_reading, line.liters), (0.0, 0.0, 0.0))

    def test_liters_estimated_absent_and_registered_refill_are_distinguished(self):
        wo = {7: {'id': 7, 'code': 'P-7', 'hourmeter_initial': 1.0, 'hourmeter_final': 9.0, 'fuel_refill_liters': 40.0}}
        self._upsert([session_item(6, work_order_id=7),                                   # recarga registrada
                      session_item(7, started_at='2026-09-10T15:00:00Z', ended_at='2026-09-10T16:00:00Z'),  # sin parte: ausente
                      ], wo)
        wizard = self._preview()
        by_uuid = {w.usage_id.session_uuid[-1]: w for w in wizard.line_ids}
        self.assertTrue(by_uuid['6'].refill_available)
        self.assertFalse(by_uuid['7'].refill_available)
        self.assertEqual(by_uuid['7'].estimated_fuel_liters, 14.5)
        by_uuid['6'].use_refill = True          # selección explícita de la recarga
        wizard.action_confirm()
        lines = {l.usage_id.session_uuid[-1]: l for l in self._lines()}
        self.assertEqual((lines['6'].liters, lines['6'].liters_source), (40.0, 'work_order_refill'))
        self.assertEqual((lines['7'].liters, lines['7'].liters_source), (0.0, 'manual'))
        self.assertEqual(lines['7'].src_estimated_fuel_liters, 14.5, 'El estimado se conserva como referencia, no como litros')

    def test_refill_is_not_used_unless_explicitly_selected(self):
        wo = {7: {'id': 7, 'code': 'P-7', 'hourmeter_initial': 1.0, 'hourmeter_final': 9.0, 'fuel_refill_liters': 40.0}}
        self._upsert([session_item(8, work_order_id=7)], wo)
        self._preview().action_confirm()
        self.assertEqual(self._lines().liters, 0.0)

    # ---- sesiones abiertas o incompletas -----------------------------------------------------
    def test_open_session_is_listed_but_not_selectable_nor_importable(self):
        self._upsert([session_item(9, ended_at=None, status='open', total_distance_m=None)])
        wizard = self._preview()
        preview = wizard.line_ids
        self.assertFalse(preview.selectable)
        self.assertFalse(preview.selected)
        self.assertIn('abierta', preview.issues)
        preview.selected = True                      # aunque alguien la marque a la fuerza
        with self.assertRaisesRegex(UserError, 'abierta o incompleta'):
            wizard.action_confirm()
        self.assertFalse(self._lines())

    def test_session_without_gps_distance_is_not_preselected(self):
        self._upsert([session_item(10, total_distance_m=None)])
        preview = self._preview().line_ids
        self.assertTrue(preview.selectable)
        self.assertFalse(preview.selected)
        self.assertIn('Sin distancia GPS', preview.issues)

    # ---- idempotencia y concurrencia -----------------------------------------------------------
    def test_repeated_confirmation_does_not_duplicate_lines(self):
        self._upsert([session_item(11)])
        wizard = self._preview()
        wizard.action_confirm()
        wizard.action_confirm()                      # doble clic
        again = self._preview()                      # otro asistente sobre lo mismo: ya no hay nada que incorporar
        self.assertFalse(again.line_ids.selectable)
        with self.assertRaisesRegex(UserError, 'Seleccione al menos'):
            again.action_confirm()
        self.assertEqual(len(self._lines()), 1)

    def test_database_constraint_blocks_duplicate_even_if_checks_are_bypassed(self):
        self._upsert([session_item(12)])
        self._preview().action_confirm()
        line = self._lines()
        with self.assertRaises(Exception), self.env.cr.savepoint():
            line.with_context(step_tracker_import=True).copy({'usage_id': line.usage_id.id, 'sheet_id': self.sheet.id})
            self.env.flush_all()

    def test_concurrent_loser_is_reported_as_skipped_not_duplicated(self):
        """Simula la carrera: entre la vista previa y la confirmación otra sesión ya creó la línea."""
        self._upsert([session_item(13)])
        wizard = self._preview()
        usage = wizard.line_ids.usage_id
        values = self.env['step.expense.tracker.import']._line_values_from_usage(usage)
        values['sheet_id'] = self.sheet.id
        self.env['step.expense.vehicle.line'].with_context(step_tracker_import=True).create(values)
        result = wizard.action_confirm()
        self.assertIn('0 recorrido(s) incorporado(s); 1 ya estaban', result['params']['message'])
        self.assertEqual(len(self._lines()), 1)

    def test_same_session_in_two_sheets_needs_explicit_override_and_km_count_once(self):
        self._upsert([session_item(14)])
        self._preview().action_confirm()
        other = self._new_sheet(self.employee)
        blocked = self._preview(sheet=other)
        self.assertFalse(blocked.line_ids.selectable)
        self.assertIn('Ya utilizada en', blocked.line_ids.issues)
        with self.assertRaises(UserError):
            blocked.line_ids.selected = True
            blocked.action_confirm()
        allowed = self._preview(sheet=other, allow_reuse=True)
        self.assertTrue(allowed.line_ids.selectable)
        allowed.line_ids.selected = True
        allowed.action_confirm()
        self.assertEqual(len(self._lines(other)), 1)
        # Dos documentos respaldan la misma sesión, pero el hecho de uso es uno: el kilometraje no se duplica.
        usage = self.env['step.tracker.usage'].search([('vehicle_id', '=', self.vehicle.id)])
        self.assertEqual(len(usage), 1)
        self.assertAlmostEqual(sum(usage.mapped('distance_km')), 12.345, places=6)
        self.assertEqual(self.env['step.expense.vehicle.line'].search_count([('usage_id', '=', usage.id)]), 2)

    # ---- períodos, medianoche y cambio de hora ------------------------------------------------------
    def test_midnight_crossing_and_session_starting_before_range(self):
        self._upsert([
            # 22:00 -> 01:00 hora de Chile (verano austral UTC-3 => 01:00Z..04:00Z del 11): cruza la medianoche
            session_item(20, started_at='2026-09-11T01:00:00Z', ended_at='2026-09-11T04:00:00Z'),
            # empieza el 9 por la noche y termina el 10: empieza antes del rango 10..10
            session_item(21, started_at='2026-09-10T02:00:00Z', ended_at='2026-09-10T05:00:00Z'),
            # empieza dentro y termina después del rango
            session_item(22, started_at='2026-09-11T02:30:00Z', ended_at='2026-09-11T08:00:00Z'),
        ])
        wizard = self._preview(date_from=date(2026, 9, 10), date_to=date(2026, 9, 10))
        by_uuid = {w.usage_id.session_uuid[-2:]: w for w in wizard.line_ids}
        self.assertTrue(by_uuid['21'].issues.count('Empieza antes del período'))
        self.assertFalse(by_uuid['21'].selected, 'Cruza el límite inferior: se asigna solo con decisión explícita')
        self.assertIn('Cruza la medianoche', by_uuid['20'].issues)
        self.assertIn('Termina después del período', by_uuid['22'].issues)
        self.assertFalse(by_uuid['22'].selected)
        # Cada sesión se asigna completa a su fecha local de inicio, una sola vez.
        for w in wizard.line_ids:
            w.selected = True
        wizard.action_confirm()
        dates = {l.usage_id.session_uuid[-2:]: l.date for l in self._lines()}
        self.assertEqual(dates['20'], date(2026, 9, 10))
        self.assertEqual(dates['21'], date(2026, 9, 9))
        self.assertEqual(dates['22'], date(2026, 9, 10))
        self.assertAlmostEqual(sum(self._lines().mapped('distance')), 3 * 12.345, places=6)

    def test_daylight_saving_change_day_has_consistent_bounds(self):
        """En Chile el 6-sep-2026 la medianoche no existe (00:00 -> 01:00): los límites deben seguir siendo coherentes."""
        wizard = self._wizard(date_from=date(2026, 9, 6), date_to=date(2026, 9, 6))
        start, end = wizard._period_utc()
        self.assertEqual(start, datetime(2026, 9, 6, 4, 0))   # primer instante del día (01:00 UTC-3)
        self.assertEqual(end, datetime(2026, 9, 7, 3, 0))     # medianoche del 7 ya en UTC-3
        self.assertEqual((end - start).total_seconds() / 3600, 23.0, 'El día del cambio dura 23 horas')
        # una sesión a las 00:30 locales del 7 pertenece al día 7, no al 6
        self._upsert([session_item(23, started_at='2026-09-07T03:30:00Z', ended_at='2026-09-07T04:30:00Z'),
                      session_item(24, started_at='2026-09-06T10:00:00Z', ended_at='2026-09-06T11:00:00Z')])
        preview = {w.usage_id.session_uuid[-2:]: w for w in wizard.action_preview() and wizard.line_ids}
        self.assertEqual(set(preview), {'24'}, 'La sesión 23 empieza el día 7 y no entra en el día 6')

    def test_period_limits(self):
        with self.assertRaises(UserError):
            self._wizard(date_from=date(2026, 9, 10), date_to=date(2026, 9, 9)).action_preview()
        with self.assertRaises(UserError):
            self._wizard(date_from=date(2026, 1, 1), date_to=date(2026, 9, 9)).action_preview()

    # ---- conductor y centro de costo --------------------------------------------------------------------
    def test_driver_differences_and_unresolved_links_are_shown_not_guessed(self):
        other_employee = self.env['hr.employee'].create({'name': 'Otro Conductor', 'company_id': self.company.id})
        self.driver.employee_id = other_employee
        self._upsert([session_item(30), session_item(31, driver_id=None, started_at='2026-09-10T16:00:00Z', ended_at='2026-09-10T17:00:00Z',
                                                     cost_center_id=None)])
        wizard = self._preview()
        by_uuid = {w.usage_id.session_uuid[-2:]: w for w in wizard.line_ids}
        self.assertIn('Conductor distinto del empleado de la rendición', by_uuid['30'].issues)
        self.assertIn('Conductor no identificado', by_uuid['31'].issues)
        self.assertIn('Sin cuenta analítica', by_uuid['31'].issues)
        self.assertFalse(by_uuid['31'].employee_id, 'No se escoge ningún conductor por defecto')
        self.assertFalse(by_uuid['31'].analytic_account_id)

    def test_sessions_of_unlinked_machine_are_counted_not_attributed(self):
        self.env['step.tracker.machine'].sudo().create({'tracker_id': 12, 'name': 'Camioneta QA', 'company_id': self.company.id})
        self._upsert([session_item(32, machine_id=12), session_item(33)])
        wizard = self._preview()
        self.assertEqual(wizard.unmapped_count, 1)
        self.assertEqual(len(wizard.line_ids), 1)
        self.assertIn('no están asociadas a ningún vehículo', wizard.coverage_message)

    # ---- cobertura del período ---------------------------------------------------------------------------------
    def test_more_than_500_sessions_are_all_listed(self):
        items = [session_item(5000 + i, started_at='2026-09-10T%02d:%02d:00Z' % (i // 60 % 24, i % 60),
                              ended_at='2026-09-10T%02d:%02d:30Z' % (i // 60 % 24, i % 60)) for i in range(0, 640)]
        tracker = FakeTracker(sessions=items, page_size=500)
        wizard = self._wizard(use_tracker_sync=True, date_from=date(2026, 9, 9), date_to=date(2026, 9, 11))
        with self.token_patch(), tracker.patch():
            wizard.action_preview()
        self.assertEqual(len(wizard.line_ids), 640)
        self.assertTrue(wizard.coverage_complete)
        self.assertIn('completo', wizard.coverage_message)

    def test_incomplete_coverage_is_never_presented_as_complete(self):
        tracker = FakeTracker(sessions=[session_item(1)], period_contract=False)
        wizard = self._wizard(use_tracker_sync=True)
        with self.token_patch(), tracker.patch():
            wizard.action_preview()
        self.assertFalse(wizard.coverage_complete)
        self.assertIn('INICIAN', wizard.coverage_message)

    def test_without_tracker_config_lists_stored_data_with_warning(self):
        self.company.step_tracker_base_url = False
        self._upsert([session_item(34)])
        wizard = self._wizard(use_tracker_sync=True)
        wizard.action_preview()
        self.assertFalse(wizard.coverage_complete)
        self.assertIn('No se consultó Tracker', wizard.coverage_message)
        self.assertEqual(len(wizard.line_ids), 1)

    def test_tracker_down_keeps_the_sheet_and_allows_retry(self):
        self._upsert([session_item(35)])
        self._preview().action_confirm()
        wizard = self._wizard(use_tracker_sync=True)
        with self.token_patch(), FakeTracker(fail=requests.ConnectTimeout('timeout')).patch():
            with self.assertRaisesRegex(UserError, 'No se modificó ningún documento'):
                wizard.action_preview()
        self.assertEqual(len(self._lines()), 1, 'La rendición conserva su estado anterior')
        with self.token_patch(), FakeTracker(sessions=[session_item(35)]).patch():
            wizard.action_preview()               # reintento seguro
        self.assertEqual(len(wizard.line_ids), 1)

    # ---- aislamiento por compañía y acceso ---------------------------------------------------------------------------
    def test_foreign_company_vehicle_and_usage_are_rejected(self):
        foreign_vehicle = self._vehicle('QA-9999', self.other_company)
        with self.assertRaisesRegex(UserError, 'pertenece a otra empresa'):
            self._wizard(vehicle=foreign_vehicle).action_preview()
        foreign_machine = self.env['step.tracker.machine'].sudo().create({
            'tracker_id': 77, 'name': 'Ajena', 'company_id': self.other_company.id, 'vehicle_id': foreign_vehicle.id})
        foreign_usage = self.env['step.tracker.usage'].sudo().create({
            'session_uuid': 'foreign-1', 'company_id': self.other_company.id, 'machine_id': foreign_machine.id,
            'started_at': datetime(2026, 9, 10, 12), 'ended_at': datetime(2026, 9, 10, 13), 'status': 'closed',
            'distance_known': True, 'distance_km': 5.0})
        with self.assertRaises(Exception), self.env.cr.savepoint():
            self.env['step.expense.vehicle.line'].with_context(step_tracker_import=True).create({
                'sheet_id': self.sheet.id, 'usage_id': foreign_usage.id, 'vehicle_id': foreign_vehicle.id, 'source': 'tracker'})

    def test_user_of_other_company_cannot_open_the_wizard_data(self):
        user_b = self.env['res.users'].create({
            'name': 'Usuario B', 'login': 'trk_exp_user_b', 'company_id': self.other_company.id,
            'company_ids': [(6, 0, [self.other_company.id])],
            'groups_id': [(6, 0, [self.env.ref('base.group_user').id])]})
        self._upsert([session_item(36)])
        with self.assertRaises(AccessError):
            self.env['step.tracker.usage'].with_user(user_b).search([]).read(['session_uuid'])
            self.sheet.with_user(user_b).read(['name'])

    def test_tracker_lines_cannot_be_forged_by_hand(self):
        self._upsert([session_item(37)])
        usage = self.env['step.tracker.usage'].search([('session_uuid', 'like', '%37')])
        with self.assertRaisesRegex(UserError, 'solo se crean con el asistente'):
            self.env['step.expense.vehicle.line'].create({
                'sheet_id': self.sheet.id, 'usage_id': usage.id, 'vehicle_id': self.vehicle.id, 'distance': 999})
        manual = self.env['step.expense.vehicle.line'].create({
            'sheet_id': self.sheet.id, 'vehicle_id': self.vehicle.id, 'route': 'Manual', 'start_reading': 10, 'end_reading': 25})
        self.assertEqual(manual.distance, 15, 'El comportamiento manual de la rendición no cambia')
        with self.assertRaisesRegex(UserError, 'solo se crean con el asistente'):
            manual.usage_id = usage

    # ---- aprobación y correcciones ---------------------------------------------------------------------------------------
    def test_corrections_are_flagged_and_survive_explicit_refresh(self):
        self._upsert([session_item(40)])
        self._preview().action_confirm()
        line = self._lines()
        self._upsert([session_item(40, total_distance_m=20000.0)])        # Tracker corrigió la distancia
        line.distance = 11.0                                              # el usuario ya había corregido
        self.assertTrue(line.is_modified)
        self.sheet.action_refresh_tracker_lines()
        self.assertEqual(line.distance, 11.0, 'La corrección manual no se sobrescribe')
        line.distance = line.src_distance_km                              # deshace la corrección
        self.assertFalse(line.is_modified)
        self.sheet.action_refresh_tracker_lines()
        self.assertAlmostEqual(line.distance, 20.0, places=6)              # actualización explícita, trazada
        self.assertIn('Actualización desde Tracker', self.sheet.message_ids[0].body)

    def test_session_change_after_approval_never_touches_the_sheet(self):
        self._upsert([session_item(41)])
        self._preview().action_confirm()
        line = self._lines()
        self.sheet.sudo().state = 'approve'
        self._upsert([session_item(41, total_distance_m=99999.0, ended_at='2026-09-10T20:00:00Z')])
        self.assertAlmostEqual(line.distance, 12.345, places=6)
        self.assertAlmostEqual(line.src_distance_km, 12.345, places=6)
        with self.assertRaisesRegex(UserError, 'en borrador'):
            self.sheet.action_refresh_tracker_lines()
        with self.assertRaisesRegex(UserError, 'ya no está en borrador'):
            line.distance = 1.0
        with self.assertRaisesRegex(UserError, 'ya no está en borrador'):
            line.unlink()
        with self.assertRaisesRegex(UserError, 'borrador'):
            self._wizard().action_preview()

    def test_source_data_fields_are_protected(self):
        self._upsert([session_item(42)])
        self._preview().action_confirm()
        line = self._lines()
        for vals in ({'src_distance_km': 1.0}, {'usage_id': False}, {'vehicle_id': False}, {'source': 'manual'}):
            with self.assertRaisesRegex(UserError, 'no se pueden editar'):
                line.write(vals)

    # ---- gastos y vehículo ---------------------------------------------------------------------------------------------------
    def test_expense_vehicle_is_explicit_and_company_checked(self):
        expense = self.sheet.expense_line_ids
        expense.step_vehicle_id = self.vehicle
        self.assertEqual(self.vehicle.step_expense_count, 1)
        self.assertEqual(self.vehicle.step_expense_sheet_count, 1)
        action = self.vehicle.action_open_step_expenses()
        self.assertEqual(self.env['hr.expense'].search(action['domain']), expense)
        foreign = self._vehicle('QA-8888', self.other_company)
        with self.assertRaises(Exception), self.env.cr.savepoint():
            expense.step_vehicle_id = foreign
        self.assertEqual(foreign.step_expense_count, 0)

    def test_tracker_credentials_are_hidden_from_regular_users(self):
        fields_info = self.env['res.company'].fields_get(['step_tracker_username', 'step_tracker_password'])
        self.assertEqual(set(fields_info), {'step_tracker_username', 'step_tracker_password'})  # el admin sí las ve
        with self.assertRaises(AccessError):
            self.company.with_user(self.employee_user).read(['step_tracker_password'])
        # el asistente funciona igual para un empleado sin privilegios: la consulta corre con sudo
        self._upsert([session_item(43)])
        wizard = self.env['step.expense.tracker.import'].with_user(self.employee_user).with_company(self.company).create({
            'sheet_id': self.sheet.id, 'vehicle_id': self.vehicle.id, 'date_from': date(2026, 9, 10),
            'date_to': date(2026, 9, 10), 'use_tracker_sync': True})
        with self.token_patch(), FakeTracker(sessions=[session_item(43)]).patch():
            wizard.action_preview()
            wizard.action_confirm()
        self.assertEqual(len(self._lines()), 1)
