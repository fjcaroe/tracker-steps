"""Fixtures de costos: compañía con plan de cuentas (Chile), vehículo vinculado y asientos publicados."""
from datetime import date

from odoo.tests.common import TransactionCase

from odoo.addons.step_tracker_usage.tests.common import session_item


class CostCase(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.currency = cls.company.currency_id
        cls.company.partner_id.tz = 'America/Santiago'
        Account = cls.env['account.account']
        cls.expense_account = Account.search([('account_type', '=', 'expense'), ('company_ids', 'in', cls.company.id)], limit=1)
        cls.payable_account = Account.search([('account_type', '=', 'liability_payable'), ('company_ids', 'in', cls.company.id)], limit=1)
        assert cls.expense_account and cls.payable_account, 'La compañía de prueba necesita plan de cuentas'
        cls.journal = cls.env['account.journal'].create({
            'name': 'Diario de costos QA', 'code': 'TCQA', 'type': 'general', 'company_id': cls.company.id})
        cls.plan_a = cls.env['account.analytic.plan'].create({'name': 'Plan QA A'})
        cls.plan_b = cls.env['account.analytic.plan'].create({'name': 'Plan QA B'})
        cls.analytic_1 = cls.env['account.analytic.account'].create({'name': 'Cuartel QA 1', 'plan_id': cls.plan_a.id})
        cls.analytic_2 = cls.env['account.analytic.account'].create({'name': 'Cuartel QA 2', 'plan_id': cls.plan_a.id})
        cls.analytic_b = cls.env['account.analytic.account'].create({'name': 'Actividad QA', 'plan_id': cls.plan_b.id})
        brand = cls.env['fleet.vehicle.model.brand'].create({'name': 'Marca costos QA'})
        fleet_model = cls.env['fleet.vehicle.model'].create({'name': 'Modelo costos QA', 'brand_id': brand.id})
        cls.vehicle = cls.env['fleet.vehicle'].create({'model_id': fleet_model.id, 'license_plate': 'CQ-0001', 'company_id': cls.company.id})
        cls.other_vehicle = cls.env['fleet.vehicle'].create({'model_id': fleet_model.id, 'license_plate': 'CQ-0002', 'company_id': cls.company.id})
        cls.employee = cls.env['hr.employee'].create({'name': 'Conductor costos QA', 'company_id': cls.company.id})
        cls.product = cls.env['product.product'].search([('can_be_expensed', '=', True)], limit=1)
        cls.machine = cls.env['step.tracker.machine'].sudo().create({
            'tracker_id': 911, 'name': 'Tractor costos QA', 'company_id': cls.company.id, 'vehicle_id': cls.vehicle.id})
        cls.driver = cls.env['step.tracker.driver'].sudo().create({
            'tracker_id': 921, 'name': 'Conductor costos QA', 'company_id': cls.company.id, 'employee_id': cls.employee.id})
        cls.tracker_center = cls.env['step.tracker.cost_center'].sudo().create({
            'tracker_id': 931, 'name': 'Centro Tracker QA', 'company_id': cls.company.id, 'analytic_account_id': cls.analytic_1.id})
        cls.usage_sync = cls.env['step.tracker.usage.sync']
        cls.service = cls.env['step.tracker.vehicle.cost']

    # ---- gastos y asientos -------------------------------------------------------
    @classmethod
    def expense(cls, amount, vehicle=None, day=date(2026, 9, 10), state='draft', currency=None, name='Gasto QA', distribution=None):
        vehicle = cls.vehicle if vehicle is None else vehicle
        expense = cls.env['hr.expense'].create({
            'name': name, 'employee_id': cls.employee.id, 'product_id': cls.product.id, 'company_id': cls.company.id,
            'total_amount_currency': amount, 'date': day, 'step_vehicle_id': vehicle.id if vehicle else False,
            'currency_id': (currency or cls.currency).id, 'analytic_distribution': distribution or False})
        sheet = cls.env['hr.expense.sheet'].create({
            'name': 'Rendición QA', 'employee_id': cls.employee.id, 'company_id': cls.company.id,
            'expense_line_ids': [(6, 0, expense.ids)]})
        if state != 'draft':
            # sheet.state se calcula: «post» = rendición aprobada con asientos publicados (ver post_expense_move)
            sheet.sudo().approval_state = {'submit': 'submit', 'approve': 'approve', 'post': 'approve'}[state]
        return expense

    @classmethod
    def post_expense_move(cls, expense, amount, day=date(2026, 9, 10), distribution=None, currency=None, amount_currency=None):
        """Asiento publicado como el que genera una rendición: gasto (con expense_id) contra cuenta por pagar."""
        company_amount = amount
        line_cost = {'account_id': cls.expense_account.id, 'name': 'Gasto', 'debit': company_amount, 'credit': 0.0,
                     'expense_id': expense.id, 'analytic_distribution': distribution}
        if currency:
            line_cost.update(currency_id=currency.id, amount_currency=amount_currency)
        line_payable = {'account_id': cls.payable_account.id, 'name': 'Por pagar', 'debit': 0.0, 'credit': company_amount,
                        'partner_id': cls.employee.work_contact_id.id}
        if currency:
            line_payable.update(currency_id=currency.id, amount_currency=-amount_currency)
        move = cls.env['account.move'].create({
            'move_type': 'entry', 'journal_id': cls.journal.id, 'date': day,
            'expense_sheet_id': expense.sheet_id.id or False,
            'line_ids': [(0, 0, line_cost), (0, 0, line_payable)]})
        move.action_post()
        return move

    @classmethod
    def usage(cls, index, start='2026-09-10T12:00:00Z', end='2026-09-10T14:00:00Z', machine_id=911, work_orders=None, **extra):
        item = session_item(index, started_at=start, ended_at=end, machine_id=machine_id, driver_id=921,
                            cost_center_id=931, **extra)
        cls.usage_sync._upsert_items(cls.company, [item], work_orders or {})
        return cls.env['step.tracker.usage'].search([('session_uuid', '=', item['id']), ('company_id', '=', cls.company.id)])
