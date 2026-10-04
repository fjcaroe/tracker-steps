"""Entrega C: costo real, pendiente, cantidades, indicadores y presupuesto."""
from datetime import date

from odoo.tests import tagged

from .common import CostCase

PERIOD = (date(2026, 9, 1), date(2026, 9, 30))


@tagged('post_install', '-at_install')
class TestVehicleCosts(CostCase):

    def _compute(self, vehicle=None, period=PERIOD, **kw):
        return self.service.compute(vehicle=vehicle or self.vehicle, date_from=period[0], date_to=period[1], **kw)

    # ---- costo real y pendiente ------------------------------------------------------------
    def test_posted_expense_counts_once_and_pending_is_separate(self):
        posted = self.expense(100000, state='post', name='Combustible contabilizado')
        self.post_expense_move(posted, 100000, distribution={str(self.analytic_1.id): 100})
        self.expense(30000, name='Peaje en borrador')
        self.expense(20000, state='approve', name='Lubricante aprobado')
        result = self._compute()
        self.assertEqual(result['real']['amount'], 100000.0)
        self.assertEqual(result['real']['lines'], 1)
        self.assertEqual(result['pending']['amount'], 50000.0)
        self.assertEqual(result['pending']['count'], 2)
        self.assertEqual({s['state'] for s in result['pending']['by_state']}, {'reported', 'approved'})
        # Odoo 18 marca «approved» al gasto de una rendición ya contabilizada: no es pendiente, es costo real.
        self.assertEqual(posted.sheet_id.state, 'post')
        self.assertEqual(posted.state, 'approved')
        self.assertNotIn(100000.0, [row['amount'] for row in result['pending']['by_state']])
        self.assertIn('Neto', result['real']['basis'])

    def test_expense_of_another_vehicle_or_company_period_is_excluded(self):
        mine = self.expense(10000, state='post')
        self.post_expense_move(mine, 10000)
        other = self.expense(77000, vehicle=self.other_vehicle, state='post')
        self.post_expense_move(other, 77000)
        unassigned = self.expense(55000, vehicle=False, state='post')
        self.post_expense_move(unassigned, 55000)
        outside = self.expense(9000, state='post', day=date(2026, 10, 2))
        self.post_expense_move(outside, 9000, day=date(2026, 10, 2))
        result = self._compute()
        self.assertEqual(result['real']['amount'], 10000.0)
        self.assertEqual(self._compute(vehicle=self.other_vehicle)['real']['amount'], 77000.0)

    def test_credit_note_reversal_and_cancelled_expense_reconcile_with_odoo(self):
        first = self.expense(100000, state='post')
        move = self.post_expense_move(first, 100000, day=date(2026, 9, 5))
        second = self.expense(40000, state='post')
        self.post_expense_move(second, 40000, day=date(2026, 9, 6))
        cancelled = self.expense(25000, state='post')
        cancelled_move = self.post_expense_move(cancelled, 25000, day=date(2026, 9, 7))
        cancelled_move.button_draft()
        cancelled_move.button_cancel()                                     # gasto cancelado: no es costo real
        self.assertEqual(self._compute()['real']['amount'], 140000.0)
        # nota de crédito / reversa publicada en el mismo período
        move._reverse_moves([{'date': date(2026, 9, 20)}], cancel=True)
        result = self._compute()
        self.assertEqual(result['real']['amount'], 40000.0, 'La reversa anula el costo original')
        # reversa en un período posterior: septiembre conserva el costo, octubre lo resta
        other = self.expense(60000, state='post', day=date(2026, 9, 8))
        other_move = self.post_expense_move(other, 60000, day=date(2026, 9, 8))
        other_move._reverse_moves([{'date': date(2026, 10, 3)}], cancel=True)
        self.assertEqual(self._compute()['real']['amount'], 100000.0)
        self.assertEqual(self._compute(period=(date(2026, 10, 1), date(2026, 10, 31)))['real']['amount'], -60000.0)
        # conciliación: el total coincide con los apuntes publicados de gasto atribuidos al vehículo
        lines = self.env['account.move.line'].search([
            ('parent_state', '=', 'posted'), ('expense_id.step_vehicle_id', '=', self.vehicle.id),
            ('date', '>=', date(2026, 9, 1)), ('date', '<=', date(2026, 9, 30)), ('account_id', '=', self.expense_account.id)])
        self.assertTrue(lines)

    def test_multi_currency_keeps_company_currency_total_and_flags_missing_rate(self):
        usd = self.env.ref('base.USD')
        expense = self.expense(100, state='post', currency=usd)
        self.post_expense_move(expense, 92000, currency=usd, amount_currency=100.0)
        result = self._compute()
        self.assertEqual(result['real']['amount'], 92000.0)
        self.assertEqual(result['real']['by_currency'], [{'currency': 'USD', 'amount': 100.0}])
        self.assertNotIn('missing_rates', result['real'])
        otr = self.env['res.currency'].with_context(active_test=False).search([('name', '=', 'OTR')])
        otr.active = True
        bad = self.expense(10, state='post', currency=otr)
        self.post_expense_move(bad, 10, currency=otr, amount_currency=10.0)
        result = self._compute()
        self.assertEqual(result['real']['missing_rates'], ['OTR'])
        self.usage(1)
        indicator = self._compute()['indicators']['cost_per_km']
        self.assertEqual(indicator['status'], 'incomplete')
        self.assertIsNone(indicator['value'], 'Sin tipo de cambio: no se presenta como costo unitario completo')
        self.assertTrue(any('OTR' in reason for reason in indicator['reasons']))

    def test_distribution_by_account_respects_percentages_and_plans(self):
        expense = self.expense(100000, state='post')
        dist = {str(self.analytic_1.id): 60.0, str(self.analytic_2.id): 30.0}
        self.post_expense_move(expense, 100000, distribution=dist)
        multi = self.expense(50000, state='post')
        self.post_expense_move(multi, 50000, distribution={'%s,%s' % (self.analytic_1.id, self.analytic_b.id): 100.0})
        result = self._compute()
        rows = {row['account']: row['amount'] for row in result['by_center']['rows']}
        self.assertEqual(rows['Cuartel QA 1'], 60000.0 + 50000.0)
        self.assertEqual(rows['Cuartel QA 2'], 30000.0)
        self.assertEqual(rows['Actividad QA'], 50000.0, 'Un apunte con dos planes se informa en cada plan, sin multiplicarse')
        self.assertEqual(result['by_center']['unassigned'], 10000.0, 'El 10% sin distribuir queda visible')
        self.assertEqual(result['real']['amount'], 150000.0, 'El total no se multiplica por planes ni porcentajes')

    # ---- cantidades -----------------------------------------------------------------------------
    def test_quantities_are_a_partition_across_contiguous_periods(self):
        self.usage(10, start='2026-09-30T20:00:00Z', end='2026-10-01T03:00:00Z')          # empieza el 30/9 (hora local)
        self.usage(11, start='2026-10-01T10:00:00Z', end='2026-10-01T11:00:00Z')
        self.usage(12, start='2026-09-01T02:00:00Z', end='2026-09-01T05:00:00Z')          # 31/8 23:00 local: agosto
        september = self._compute()['quantities']
        october = self._compute(period=(date(2026, 10, 1), date(2026, 10, 31)))['quantities']
        august = self._compute(period=(date(2026, 8, 1), date(2026, 8, 31)))['quantities']
        total = round(september['km']['value'] + october['km']['value'] + august['km']['value'], 3)
        self.assertEqual(total, round(3 * 12.345, 3), 'Cada sesión cae en un único período')
        self.assertEqual((august['sessions'], september['sessions'], october['sessions']), (1, 1, 1))

    def test_open_and_no_distance_sessions_are_excluded_and_reported(self):
        self.usage(20)
        self.usage(21, total_distance_m=None, start='2026-09-11T12:00:00Z', end='2026-09-11T13:00:00Z')
        self.usage(22, status='open', total_distance_m=None, start='2026-09-12T12:00:00Z', end=None)
        q = self._compute()['quantities']
        self.assertAlmostEqual(q['km']['value'], 12.345, places=3)
        self.assertEqual(q['excluded'], {'open': 1, 'closed_without_distance': 1})
        self.assertAlmostEqual(q['session_hours']['value'], 3.0, places=2)   # 2 h + 1 h cerradas; la abierta no cuenta

    def test_session_hours_are_not_engine_hours_and_hourmeter_counts_each_work_order_once(self):
        wo = {7: {'id': 7, 'code': 'P-7', 'hourmeter_initial': 100.0, 'hourmeter_final': 108.0}}
        self.usage(30, work_order_id=7, work_orders=wo)
        self.usage(31, work_order_id=7, work_orders=wo, start='2026-09-10T16:00:00Z', end='2026-09-10T17:00:00Z')
        self.usage(32, start='2026-09-11T12:00:00Z', end='2026-09-11T14:00:00Z')        # 2 h de sesión, sin lectura
        q = self._compute()['quantities']
        self.assertAlmostEqual(q['session_hours']['value'], 5.0, places=2)
        self.assertEqual(q['hourmeter_hours']['value'], 8.0, 'El parte compartido se cuenta una sola vez')
        self.assertEqual(q['hourmeter_hours']['work_orders'], 1)
        self.assertEqual(q['hourmeter_hours']['sessions_without_reading'], 1)
        self.assertIn('no horas de motor', q['session_hours']['label'])

    # ---- indicadores ------------------------------------------------------------------------------
    def _complete_case(self):
        self.usage(40, end='2026-09-10T16:00:00Z')                        # 4 h, 12,345 km
        expense = self.expense(123450, state='post')
        self.post_expense_move(expense, 123450)

    def test_unit_costs_complete(self):
        self._complete_case()
        result = self._compute()
        km = result['indicators']['cost_per_km']
        self.assertEqual(km['status'], 'ok')
        self.assertAlmostEqual(km['value'], 10000.0, places=2)
        hour = result['indicators']['cost_per_hour']
        self.assertEqual(hour['status'], 'ok')
        self.assertIn('sesión', hour['label'])
        self.assertAlmostEqual(hour['value'], 30862.5, places=2)

    def test_hourly_metric_is_labelled_and_needs_its_own_readings(self):
        self._complete_case()
        result = self._compute(hourly_metric='hourmeter')
        hour = result['indicators']['cost_per_hour']
        self.assertIn('horómetro', hour['label'])
        self.assertEqual(hour['status'], 'unavailable', '4 h de sesión sin lecturas no inventan horas de motor')
        self.assertIsNone(hour['value'])

    def test_unavailable_when_denominator_is_zero_or_nothing_posted(self):
        self.expense(5000, state='post')
        self.post_expense_move(self.expense(5000, state='post'), 5000)
        no_km = self._compute()['indicators']['cost_per_km']
        self.assertEqual((no_km['status'], no_km['value']), ('unavailable', None))
        self.assertTrue(any('kilómetros GPS' in r for r in no_km['reasons']))
        self.usage(41)
        none_posted = self._compute(vehicle=self.other_vehicle)
        self.assertEqual(none_posted['indicators']['cost_per_km']['status'], 'unavailable')

    def test_partial_ratio_is_not_presented_as_complete(self):
        self._complete_case()
        self.expense(50000, state='approve', name='Sin contabilizar')
        result = self._compute()
        km = result['indicators']['cost_per_km']
        self.assertEqual(km['status'], 'incomplete')
        self.assertIsNone(km['value'])
        self.assertAlmostEqual(km['partial'], 10000.0, places=2)
        # gasto de una rendición que usa el vehículo pero sin vehículo asignado: queda no atribuido
        sheet = self.env['hr.expense.sheet'].create({
            'name': 'Rendición mixta', 'employee_id': self.employee.id, 'company_id': self.company.id})
        loose = self.env['hr.expense'].create({
            'name': 'Sin vehículo', 'employee_id': self.employee.id, 'product_id': self.product.id, 'company_id': self.company.id,
            'total_amount_currency': 7000, 'date': date(2026, 9, 12), 'sheet_id': sheet.id})
        self.env['step.expense.vehicle.line'].create({
            'sheet_id': sheet.id, 'vehicle_id': self.vehicle.id, 'date': date(2026, 9, 12), 'route': 'Manual'})
        result = self._compute()
        self.assertEqual(result['unattributed']['count'], 1)
        self.assertEqual(result['unattributed']['amount'], 7000.0)
        self.assertTrue(any('no tienen vehículo asignado' in r for r in result['indicators']['cost_per_km']['reasons']))
        self.assertEqual(loose.step_vehicle_id.id, False, 'No se reparte ni se asigna solo')

    def test_excluded_sessions_make_unit_cost_incomplete(self):
        self._complete_case()
        self.usage(42, total_distance_m=None, start='2026-09-11T12:00:00Z', end='2026-09-11T13:00:00Z')
        km = self._compute()['indicators']['cost_per_km']
        self.assertEqual(km['status'], 'incomplete')
        self.assertTrue(any('sin distancia GPS' in r for r in km['reasons']))


@tagged('post_install', '-at_install')
class TestCenterCosts(CostCase):

    def _center(self, account=None, code='CQ1'):
        return self.env['step.management.cost.center'].create({
            'name': 'Centro %s' % code, 'code': code, 'company_id': self.company.id,
            'analytic_account_id': (account or self.analytic_1).id})

    def _compute(self, center, period=PERIOD):
        return self.service.compute(center=center, date_from=period[0], date_to=period[1])

    def test_center_real_uses_distribution_percentages_once(self):
        center = self._center()
        e1 = self.expense(100000, state='post')
        self.post_expense_move(e1, 100000, distribution={str(self.analytic_1.id): 60.0, str(self.analytic_2.id): 40.0})
        e2 = self.expense(50000, state='post')
        self.post_expense_move(e2, 50000, distribution={'%s,%s' % (self.analytic_1.id, self.analytic_b.id): 100.0})
        result = self._compute(center)
        self.assertEqual(result['real']['amount'], 60000.0 + 50000.0)
        self.assertEqual(result['real']['lines'], 2)
        other = self._compute(self._center(self.analytic_b, 'CQB'))
        self.assertEqual(other['real']['amount'], 50000.0, 'El plan B ve el apunte de dos planes una sola vez')

    def test_center_pending_uses_distribution_and_excludes_posted(self):
        center = self._center()
        self.expense(10000, distribution={str(self.analytic_1.id): 50.0}, name='Pendiente repartido')
        posted = self.expense(99000, state='post', distribution={str(self.analytic_1.id): 100.0})
        self.post_expense_move(posted, 99000, distribution={str(self.analytic_1.id): 100.0})
        result = self._compute(center)
        self.assertEqual(result['pending']['amount'], 5000.0)
        self.assertEqual(result['real']['amount'], 99000.0)

    def test_shared_analytic_account_is_flagged_and_budget_not_compared(self):
        first = self._center(code='CQ1')
        second = self._center(code='CQ2')
        result = self._compute(first, period=(date(2026, 9, 1), date(2026, 9, 30)))
        self.assertEqual(result['shared_account'], [second.display_name])
        self.assertFalse(result['budget']['available'])
        self.assertIn('comparten la cuenta analítica', result['budget']['reason'])

    def test_center_without_analytic_account_is_unavailable(self):
        center = self.env['step.management.cost.center'].create({'name': 'Sin cuenta', 'code': 'CQX', 'company_id': self.company.id})
        result = self._compute(center)
        self.assertFalse(result['real']['available'])
        self.assertIn('cuenta analítica', result['real']['reason'])

    def test_center_operational_quantities_come_from_its_analytic_account(self):
        center = self._center()
        self.usage(50)
        result = self._compute(center)
        self.assertAlmostEqual(result['quantities']['km']['value'], 12.345, places=3)
        self.assertNotIn('indicators', result, 'El costo unitario solo se define por vehículo')

    # ---- presupuesto ---------------------------------------------------------------------------------
    def _budget(self, center, amount, currency=None, state='approved'):
        group = self.env['step.management.budget.group'].create({
            'name': 'Combustible QA', 'code': 'CQ-G%s' % amount, 'company_id': self.company.id, 'flow_type': 'cost'})
        budget = self.env['step.management.operational.budget'].create({
            'description': 'Presupuesto QA', 'season': '2026/2027', 'date': date(2026, 9, 1), 'company_id': self.company.id,
            'currency_id': (currency or self.currency).id, 'budget_type': 'general'})
        line = self.env['step.management.budget.line'].create({
            'budget_id': budget.id, 'center_id': center.id, 'category': 'other', 'group_id': group.id,
            'indicator': 'Combustible', 'calculation_mode': 'direct', 'direct_amount': amount,
            'month_ids': [(0, 0, {'month': 'sep', 'direct_amount': amount})]})
        self.env.cr.execute('UPDATE step_management_operational_budget SET state=%s WHERE id=%s', [state, budget.id])
        budget.invalidate_recordset(['state'])
        return budget, line

    def test_budget_deviation_same_period_currency_and_scope(self):
        center = self._center()
        self._budget(center, 200000.0)
        posted = self.expense(250000, state='post')
        self.post_expense_move(posted, 250000, distribution={str(self.analytic_1.id): 100.0})
        result = self._compute(center)
        budget = result['budget']
        self.assertTrue(budget['available'], budget)
        self.assertEqual(budget['amount'], 200000.0)
        self.assertEqual(budget['variance'], 50000.0)
        self.assertEqual(budget['variance_percent'], 25.0)

    def test_budget_not_compared_for_partial_months_or_unapproved(self):
        center = self._center()
        self._budget(center, 200000.0, state='draft')
        self.assertIn('No hay presupuesto aprobado', self._compute(center)['budget']['reason'])
        partial = self._compute(center, period=(date(2026, 9, 1), date(2026, 9, 15)))
        self.assertIn('meses completos', partial['budget']['reason'])

    def test_budget_in_other_currency_needs_an_exchange_rate(self):
        center = self._center()
        otr = self.env['res.currency'].with_context(active_test=False).search([('name', '=', 'OTR')])
        self._budget(center, 1000.0, currency=otr)
        result = self._compute(center)
        self.assertFalse(result['budget']['available'])
        self.assertIn('tipo de cambio', result['budget']['reason'])
