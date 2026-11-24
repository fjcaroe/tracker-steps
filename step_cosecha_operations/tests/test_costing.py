from lxml import etree
from odoo import Command
from odoo.exceptions import UserError, AccessError
from odoo.tests import TransactionCase, tagged
from odoo.tests.common import new_test_user


@tagged('post_install', '-at_install')
class HarvestCostingCase(TransactionCase):
    def setUp(self):
        super().setUp()
        self.company = self.env['res.company'].create({'name': 'Private T235 harvest',
            'gratifica': 0, 'step_seguro': 0, 'step_feriado': 0, 'step_ias': 0,
            'sema_corrida_legal': False})
        self.env = self.env(context=dict(self.env.context, allowed_company_ids=self.company.ids))
        self.kg = self.env.ref('uom.product_uom_kgm')
        self.box = self.env['uom.uom'].create({'name': 'Private T235 box',
            'category_id': self.env.ref('uom.product_uom_unit').category_id.id,
            'uom_type': 'bigger', 'factor_inv': 3, 'rounding': 1})
        self.labor = self.env['product.template'].create({'name': 'Private T235 harvest labor',
            'type': 'service', 'cosecha': True, 'uom_id': self.kg.id, 'uom_po_id': self.kg.id})
        self.tariff = self.env['product.pricelist'].create({'name': 'Private T235 rate',
            'company_id': self.company.id, 'currency_id': self.company.currency_id.id,
            'cosecha': True, 'group_type': 'propio'})
        self.rule = self.env['product.pricelist.item'].create({'pricelist_id': self.tariff.id,
            'product_tmpl_id': self.labor.id, 'uom_id': self.box.id, 'fixed_price': 1575,
            'min_quantity': 10, 'applied_on': '1_product',
            'date_start': '2026-11-23 13:00:00', 'date_end': '2026-11-30 13:00:00'})

    def harvest(self, **values):
        return self.env['step.cosecha.registry'].create({'name': 'Private T235 sheet',
            'company_id': self.company.id, 'type_tarea': 'propio', 'state': 'costo',
            'date': '2026-11-24 12:00:00', 'product_uom_id': self.box.id,
            'labor_id': self.labor.id, 'pricelist_id': self.tariff.id,
            'registry_line': [Command.create({'quantity': 15, 'hrs': 8, 'sueldo_base': 18451.77})],
            **values})

    def original_inputs(self, record):
        self.env.flush_all()
        self.env.cr.execute('SELECT id,labor_id,uom_id,quantity,cant_minima,tarifa,sueldo_base '
            'FROM step_cosecha_registry_line WHERE registry_id=%s ORDER BY id', [record.id])
        return self.env.cr.fetchall()

    def test_reported_empty_line_labor_and_unit_use_the_header(self):
        record = self.harvest()
        line = record.registry_line
        self.assertFalse(line.labor_id)
        self.assertFalse(line.uom_id)
        self.assertEqual(line.harvest_min_quantity, 10)
        self.assertEqual(line.harvest_unit_price, 1575)
        self.assertEqual(line.total_trato, 23625)
        self.assertAlmostEqual(line.variable_trato, 5173.23)
        self.assertAlmostEqual(line.harvest_salary_base, 18451.77)

    def test_minimum_target_remains_visible_below_target_with_zero_variable(self):
        line = self.harvest().registry_line
        line.quantity = 5
        self.assertEqual(line.harvest_min_quantity, 10)
        self.assertEqual(line.harvest_unit_price, 1575)
        self.assertEqual(line.total_trato, 7875)
        self.assertEqual(line.variable_trato, 0)

    def test_recorded_unit_selects_the_rate_instead_of_the_labor_product_unit(self):
        self.rule.copy({'uom_id': self.kg.id, 'fixed_price': 700, 'min_quantity': 0})
        record = self.harvest()
        self.assertEqual(record.registry_line.harvest_unit_price, 1575)
        record.product_uom_id = self.kg
        self.assertEqual(record.registry_line.harvest_unit_price, 700)
        self.assertEqual(record.registry_line.total_trato, 10500)

    def test_labor_without_a_variant_never_matches_an_unrelated_template_rate(self):
        record = self.harvest()
        unresolved = self.env['product.template'].new({'name': 'Private unresolved T235 labor',
            'uom_id': self.kg.id, 'uom_po_id': self.kg.id})
        item, price, minimum = record._harvest_cost_rate(unresolved, 15, self.box)
        self.assertFalse(item)
        self.assertEqual(price, 0)
        self.assertEqual(minimum, 0)

    def test_compatible_unit_converts_both_price_and_minimum(self):
        self.rule.write({'uom_id': self.kg.id, 'fixed_price': 1000, 'min_quantity': 10})
        grams = self.env.ref('uom.product_uom_gram')
        record = self.harvest(product_uom_id=grams.id)
        record.registry_line.quantity = 15000
        self.assertEqual(record.registry_line.harvest_unit_price, 1)
        self.assertEqual(record.registry_line.harvest_min_quantity, 10000)
        self.assertEqual(record.registry_line.total_trato, 15000)

    def test_reading_costs_does_not_rewrite_original_worksheet_inputs(self):
        record = self.harvest()
        before = self.original_inputs(record)
        record.registry_line.read(['harvest_min_quantity', 'harvest_unit_price',
            'harvest_salary_base', 'total_trato', 'variable_trato', 'cost_empresa'])
        record._dashboard_metrics()
        record.registry_line.with_context(step_harvest_native_cost_preview=True).read([
            'harvest_unit_price', 'cost_empresa'])
        self.assertEqual(self.original_inputs(record), before)

    def test_unsaved_form_line_uses_its_actual_inputs(self):
        record = self.harvest()
        line = self.env['step.cosecha.registry.line'].new({'registry_id': record.id,
            'quantity': 17, 'hrs': 8, 'sueldo_base': 18451.77})
        self.assertEqual(line.harvest_unit_price, 1575)
        self.assertEqual(line.total_trato, 26775)
        self.assertAlmostEqual(line.variable_trato, 8323.23)

    def test_dashboard_virtual_costs_match_the_worksheet_preview(self):
        record = self.harvest()
        before = self.original_inputs(record)
        self.assertEqual(record.registry_line.cost_empresa, 23625)
        self.assertEqual(record._dashboard_metrics()['total_cost'], 23625)
        self.assertEqual(self.original_inputs(record), before)

    def test_costing_and_return_to_approved_keep_lines_and_snapshot_native_inputs(self):
        record = self.harvest(state='apro')
        line = record.registry_line
        record.action_costeo()
        self.assertEqual(record.state, 'costo')
        self.assertEqual(line.labor_id, self.labor)
        self.assertEqual(line.uom_id, self.box)
        self.assertEqual(line.tarifa, 1575)
        self.assertEqual(line.cant_minima, 10)
        record.action_return_approved()
        self.assertEqual(record.state, 'apro')
        self.assertEqual(record.registry_line, line)
        self.rule.fixed_price = 1600
        record.action_costeo()
        self.assertEqual(line.tarifa, 1600)
        self.assertEqual(line.total_trato, 24000)

    def test_posted_worksheet_keeps_its_snapshot_after_rate_changes(self):
        record = self.harvest(state='apro')
        record.action_costeo()
        record.state = 'cont'
        before = self.original_inputs(record)
        self.rule.fixed_price = 9999
        self.assertEqual(record.registry_line.harvest_unit_price, 1575)
        self.assertEqual(record.registry_line.total_trato, 23625)
        self.assertEqual(self.original_inputs(record), before)
        with self.assertRaises(UserError):
            record.action_return_approved()

    def test_missing_or_expired_rate_prevents_costing_without_using_another_unit(self):
        record = self.harvest(state='apro')
        self.assertEqual(record.registry_line.harvest_unit_price, 1575)
        self.rule.date_end = '2026-11-23 23:59:00'
        self.assertEqual(record.registry_line.harvest_unit_price, 0)
        with self.assertRaises(UserError):
            record.action_costeo()
        self.assertEqual(record.state, 'apro')
        self.rule.date_end = '2026-11-30 13:00:00'
        record.product_uom_id = self.env.ref('uom.product_uom_hour')
        with self.assertRaises(UserError):
            record.action_costeo()
        self.assertEqual(record.state, 'apro')

    def test_contractor_costing_uses_the_same_native_header_unit(self):
        self.tariff.group_type = 'contratista'
        record = self.harvest(type_tarea='contratista', registry_line=[],
            registry_tarja_line=[Command.create({'quantity': 16, 'hrs': 8})])
        line = record.registry_tarja_line
        self.assertEqual(line.harvest_unit_price, 1575)
        self.assertEqual(line.harvest_min_quantity, 10)
        self.assertEqual(line.trato_total, 25200)
        self.assertIsNotNone(line.employee_id_domain)

    def test_native_accounting_uses_the_saved_rate_when_it_changes_state(self):
        expense, liability = self.env['account.account'].create([
            {'name': 'Private T235 expense', 'code': '982351', 'account_type': 'expense',
             'company_ids': [Command.set(self.company.ids)]},
            {'name': 'Private T235 liability', 'code': '982352', 'account_type': 'liability_current',
             'company_ids': [Command.set(self.company.ids)]}])
        journal = self.env['account.journal'].create({'name': 'Private T235 costing',
            'code': 'H235', 'type': 'general', 'company_id': self.company.id,
            'default_account_id': expense.id, 'account_control_ids': [Command.set(liability.ids)]})
        self.company.step_cosecha_journal_id = journal
        accounts = self.env['account.analytic.account']
        for label in ('Season', 'Center', 'Activity'):
            plan = self.env['account.analytic.plan'].create({'name': 'Private T235 '+label})
            accounts |= accounts.create({'name': 'Private T235 '+label,
                'plan_id': plan.id, 'company_id': self.company.id})
        season, center, activity = accounts
        if 'cost_id' in center._fields:
            center.cost_id = center
            activity.cost_id = activity
        self.env['step.temporada'].create({'name': 'Private T235 season',
            'start_date': '2098-01-01', 'end_date': '2098-12-31',
            'company_id': self.company.id, 'cost_id': season.id})
        self.labor.actividad_id = activity
        self.rule.write({'date_start': '2098-01-01', 'date_end': '2098-12-31'})
        # Native legacy lookup is global. Isolate its rules inside this rolled-
        # back test transaction without changing any live configuration.
        rules = self.env['step.haber.costeo']
        rules.search([('active', '=', True)]).write({'active': False})
        for kind in ('provi_sueldo', 'provi_seguro', 'provi_feriado', 'provi_ias'):
            values = {'name': 'Private T235 '+kind, 'type': kind, 'active': True,
                'debe_account_id': expense.id, 'haber_account_id': liability.id}
            if 'company_id' in rules._fields:
                values['company_id'] = self.company.id
            rules.create(values)
        operator = new_test_user(self.env.with_context(no_reset_password=True), login='private_t235_accounting',
            groups='base.group_user,hr.group_hr_user,account.group_account_manager',
            company_id=self.company.id, company_ids=[Command.set(self.company.ids)])
        record = self.harvest(state='apro', date='2098-06-01', cost_id=center.id).with_user(operator)
        record.action_costeo()
        record.action_conta()
        self.assertFalse(record.env.su)
        self.assertEqual(record.state, 'cont')
        self.assertEqual(record.invoice_id.state, 'draft')
        self.assertEqual(sum(record.invoice_id.line_ids.mapped('debit')), 23625)
        self.assertEqual(sum(record.invoice_id.line_ids.mapped('credit')), 23625)
        self.assertEqual(record.registry_line.tarifa, 1575)
        with self.assertRaises(UserError):
            record.action_return_approved()
        with self.assertRaises(UserError):
            record.action_conta()

    def test_return_access_and_native_form_and_menu(self):
        record = self.harvest()
        portal = new_test_user(self.env.with_context(no_reset_password=True), login='private_t235_portal', groups='base.group_portal')
        with self.assertRaises(AccessError):
            record.with_user(portal).action_return_approved()
        record.cos_recibida = True
        with self.assertRaises(UserError):
            record.action_return_approved()
        view = self.env.ref('step_cosecha.view_step_cosecha_registry_form')
        arch = etree.fromstring(record.get_view(view_id=view.id, view_type='form')['arch'])
        self.assertTrue(arch.xpath("//header/button[@name='action_return_approved']"))
        for name in ('harvest_min_quantity', 'harvest_unit_price', 'harvest_salary_base'):
            self.assertTrue(arch.xpath("//page[@name='movi_line']//field[@name='%s']" % name))
        self.assertEqual(self.env.ref('step_cosecha.action_step_cosecha_costo_pro').res_model,
            'step.cosecha.registry')
