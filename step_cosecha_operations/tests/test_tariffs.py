from lxml import etree
from odoo import Command, fields
from odoo.exceptions import ValidationError
from odoo.tests import Form, TransactionCase, tagged
from odoo.tools.safe_eval import safe_eval


@tagged('post_install', '-at_install')
class HarvestTariffCase(TransactionCase):
    def setUp(self):
        super().setUp()
        self.company = self.env['res.company'].create({'name': 'Private T231 harvest'})
        self.env = self.env(context=dict(self.env.context, allowed_company_ids=self.company.ids))
        self.kg = self.env.ref('uom.product_uom_kgm')
        self.labor = self.env['product.template'].create({
            'name': 'Private harvest to process', 'type': 'service', 'cosecha': True,
            'uom_id': self.kg.id, 'uom_po_id': self.kg.id})
        self.view = self.env.ref('step_cosecha_operations.harvest_pricelist_form')

    def tariff(self, kind='propio'):
        return self.env['product.pricelist'].create({
            'name': 'Private T231 rate', 'cosecha': True, 'group_type': kind,
            'company_id': self.company.id, 'currency_id': self.company.currency_id.id})

    def test_tariff_menus_open_existing_rates_before_the_native_form(self):
        for kind in ('propio', 'contratista'):
            action = self.env.ref('step_cosecha.step_pricelist_action_' + kind + '_cosecha')
            views = action._get_action_dict()['views']
            self.assertEqual(views[0], (False, 'list'))
            self.assertIn((self.view.id, 'form'), views[1:])

    def test_reported_form_save_own_and_contractor(self):
        for kind in ('propio', 'contratista'):
            ctx = {'step_propio_cosecha' if kind == 'propio' else 'step_contra_cosecha': 1}
            with Form(self.env['product.pricelist'].with_context(**ctx), view=self.view) as form:
                form.name = 'Private T231 form ' + kind
                self.assertEqual(form.company_id, self.company)
                form.date_init = fields.Date.to_date('2026-11-01')
                form.date_end = fields.Date.to_date('2026-12-31')
                with form.item_ids.new() as line:
                    line.labor_id = self.labor
                    self.assertEqual(line.uom_id, self.kg)
                    line.fixed_price = 500
                    line.min_quantity = 40
                    line.can_std = 50
                    line.can_max = 80
            tariff = form.record
            self.assertTrue(tariff.cosecha)
            self.assertEqual(tariff.group_type, kind)
            self.assertEqual(tariff.item_ids.labor_id, self.labor)
            self.assertEqual(tariff.item_ids.product_tmpl_id, self.labor)
            self.assertEqual(tariff.item_ids.uom_id, self.kg)
            self.assertEqual(tariff.item_ids.fixed_price, 500)
            price, rule = tariff._get_product_price_rule(self.labor.product_variant_id, 40,
                date=fields.Datetime.to_datetime('2026-11-23 12:00:00'))
            self.assertEqual(rule, tariff.item_ids.id)
            self.assertEqual(price, 500)
            with Form(tariff, view=self.view) as edited:
                with edited.item_ids.edit(0) as line:
                    line.fixed_price = 550
            self.assertEqual(tariff.item_ids.fixed_price, 550)

    def test_native_product_api_and_explicit_unit(self):
        tariff = self.tariff()
        rule = self.env['product.pricelist.item'].create({
            'pricelist_id': tariff.id, 'product_tmpl_id': self.labor.id,
            'applied_on': '1_product', 'fixed_price': 500})
        self.assertEqual(rule.labor_id, self.labor)
        self.assertEqual(rule.uom_id, self.kg)
        grams = self.env.ref('uom.product_uom_gram')
        rule.write({'uom_id': grams.id, 'fixed_price': 1})
        self.assertEqual(rule.uom_id, grams)
        rule.write({'fixed_price': 2})
        self.assertEqual(rule.uom_id, grams)

    def test_variant_rule_keeps_native_variant(self):
        product = self.labor.product_variant_id
        rule = self.env['product.pricelist.item'].create({
            'pricelist_id': self.tariff().id, 'product_id': product.id,
            'applied_on': '0_product_variant', 'fixed_price': 500})
        rule.write({'fixed_price': 600})
        self.assertEqual(rule.product_id, product)
        self.assertEqual(rule.applied_on, '0_product_variant')
        self.assertEqual(rule.labor_id, self.labor)

    def test_cost_centers_include_native_child_plan_not_other_dimensions(self):
        root = self.env['account.analytic.plan'].create({'name': 'Centro Costos'})
        child = self.env['account.analytic.plan'].create({'name': 'Private orchard', 'parent_id': root.id})
        other = self.env['account.analytic.plan'].create({'name': 'Private activity'})
        foreign = self.env['res.company'].create({'name': 'Private foreign T231'})
        accounts = self.env['account.analytic.account'].create([
            {'name': 'Private valid center', 'plan_id': child.id, 'company_id': self.company.id},
            {'name': 'Private wrong dimension', 'plan_id': other.id, 'company_id': self.company.id},
            {'name': 'Private foreign center', 'plan_id': root.id, 'company_id': foreign.id}])
        arch = etree.fromstring(self.env['product.pricelist'].get_view(
            view_id=self.view.id, view_type='form')['arch'])
        node = arch.xpath("//field[@name='cost_ids']")[0]
        domain = safe_eval(node.get('domain'), {'company_id': self.company.id})
        selected = self.env['account.analytic.account'].search(domain)
        self.assertIn(accounts[0], selected)
        self.assertNotIn(accounts[1], selected)
        self.assertNotIn(accounts[2], selected)
        shared_domain = safe_eval(node.get('domain'), {'company_id': False,
            'context': {'allowed_company_ids': self.company.ids}})
        shared = self.env['account.analytic.account'].search(shared_domain)
        self.assertIn(accounts[0], shared)
        self.assertNotIn(accounts[2], shared)
        tariff = self.tariff()
        with Form(tariff, view=self.view) as form:
            form.cost_ids.add(accounts[0])
        self.assertEqual(tariff.cost_ids, accounts[0])
        for kind in ('propio', 'contratista'):
            action = self.env.ref('step_cosecha.step_pricelist_action_' + kind + '_cosecha')
            self.assertIn((self.view.id, 'form'), action._get_action_dict()['views'])

    def test_ordinary_validation_is_unchanged(self):
        if 'step_advance_price' not in self.env['product.pricelist']._fields:
            self.skipTest('The producer validation is not installed in this database')
        ordinary = self.env['product.pricelist'].create({'name': 'Private ordinary rate'})
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self.env['product.pricelist.item'].create({
                'pricelist_id': ordinary.id, 'product_tmpl_id': self.labor.id,
                'applied_on': '1_product', 'fixed_price': 500})
