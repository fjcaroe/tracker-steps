from odoo import Command
from odoo.exceptions import AccessError, ValidationError, UserError
from odoo.tests import TransactionCase, Form, tagged, new_test_user


@tagged('post_install', '-at_install')
class TestMasters(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.a = cls.env.company
        cls.b = cls.env['res.company'].create({'name': 'QA shared branch', 'parent_id': cls.a.id})
        cls.c = cls.env['res.company'].create({'name': 'QA unrelated company'})
        cls.user = new_test_user(cls.env, login='qa-shared-master',
            groups='base.group_user,base.group_multi_company,stock.group_stock_manager,step_management_costs.group_management_manager,sales_team.group_sale_manager',
            company_id=cls.a.id, company_ids=[Command.set((cls.a | cls.b).ids)])
        cls.models = ('step.fundo', 'step.management.fruit.category', 'step.management.fruit.quality', 'step.fruit.color')
        cls.category = cls.env['step.management.fruit.category'].create({'name': 'QA shared category', 'code': 'QA-MC-C',
            'company_id': cls.a.id, 'company_ids': [Command.set((cls.a | cls.b).ids)]})

    def make(self, model, **values):
        vals = {'name': 'QA shared master', 'company_id': self.a.id}
        if 'code' in self.env[model]._fields:
            vals['code'] = 'QA-MC-X'
        vals.update(values)
        return self.env[model].create(vals)

    def test_original_company_default(self):
        for name in self.models:
            record = self.make(name)
            self.assertEqual(record.company_ids, self.a)

    def test_all_five_shared_across_branch(self):
        for name in (*self.models, 'step.management.fruit.class'):
            vals = {'company_ids': [Command.set((self.a | self.b).ids)]}
            if name.endswith('.class'):
                vals['category_id'] = self.category.id
            record = self.make(name, **vals)
            branch = record.with_user(self.user).with_context(allowed_company_ids=self.b.ids)
            self.assertIn(record.id, branch.search([('id', '=', record.id)]).ids)
            branch.read(['name', 'company_ids'])
            branch.write({'name': 'QA edited from branch'})
            self.assertEqual(record.company_id, self.a)

    def test_unselected_company_cannot_read(self):
        record = self.make('step.fruit.color')
        user = new_test_user(self.env, login='qa-foreign-master', groups='sales_team.group_sale_manager',
                             company_id=self.c.id, company_ids=[Command.set(self.c.ids)])
        other = record.with_user(user).with_context(allowed_company_ids=self.c.ids)
        self.assertFalse(other.search([('id', '=', record.id)]))
        with self.assertRaises(AccessError):
            other.read(['name'])

    def test_empty_and_original_removal_rejected(self):
        record = self.make('step.fundo')
        for companies in ([], self.b.ids):
            with self.assertRaises(ValidationError), self.cr.savepoint():
                record.write({'company_ids': [Command.set(companies)]})

    def test_unauthorized_company_assignment_rejected(self):
        model = self.env['step.fruit.color'].with_user(self.user).with_context(allowed_company_ids=(self.a | self.b).ids)
        with self.assertRaises(AccessError), self.cr.savepoint():
            model.create({'name': 'QA forbidden', 'code': 'QA-FORBIDDEN', 'company_ids': [Command.set((self.a | self.c).ids)]})
        record = self.make('step.fruit.color')
        with self.assertRaises(AccessError), self.cr.savepoint():
            record.with_env(model.env).write({'company_ids': [Command.set((self.a | self.c).ids)]})

    def test_overlapping_codes_rejected(self):
        self.make('step.fruit.color')
        second = self.make('step.fruit.color', company_id=self.b.id)
        with self.assertRaises(ValidationError), self.cr.savepoint():
            second.write({'company_ids': [Command.set((self.a | self.b).ids)]})

    def test_category_covers_all_class_companies(self):
        fruit_class = self.make('step.management.fruit.class', category_id=self.category.id,
                               company_ids=[Command.set((self.a | self.b).ids)])
        with self.assertRaises(ValidationError), self.cr.savepoint():
            fruit_class.write({'company_ids': [Command.set((self.a | self.b | self.c).ids)]})
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self.category.write({'company_ids': [Command.set(self.a.ids)]})

    def test_native_picking_consistency(self):
        warehouse = self.env['stock.warehouse'].search([('company_id', '=', self.b.id)], limit=1)
        self.assertTrue(warehouse)
        pick = self.env['stock.picking'].with_company(self.b).create({'picking_type_id': warehouse.in_type_id.id,
            'location_id': self.env.ref('stock.stock_location_suppliers').id,
            'location_dest_id': warehouse.lot_stock_id.id, 'fruit_category_id': self.category.id})
        pick._check_company(['fruit_category_id'])
        self.assertEqual(pick.company_id, self.b)
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self.category.write({'company_ids': [Command.set(self.a.ids)]})
        foreign = self.make('step.management.fruit.category', code='QA-FOREIGN-CAT', company_id=self.c.id)
        with self.assertRaises(UserError), self.cr.savepoint():
            pick.write({'fruit_category_id': foreign.id})

    def test_native_fundo_form_and_menu(self):
        model = self.env['step.fundo'].with_user(self.user).with_context(allowed_company_ids=(self.a | self.b).ids)
        with Form(model, view='step_hr.view_step_fundo_form') as form:
            form.name = 'QA native shared fundo'
            form.company_ids.add(self.b)
        self.assertEqual(set(form.record.company_ids.ids), set((self.a | self.b).ids))
        menu = self.env.ref('step_agriculture_multicompany.packing_fundos')
        self.assertEqual(menu.action, self.env.ref('step_producers.action_step_producers_fundo'))
        self.assertEqual(menu.parent_id, self.env.ref('step_packing_operations.menu_packing_operations_masters'))

    def test_origin_is_preserved(self):
        record = self.make('step.fundo')
        with self.assertRaises(ValidationError), self.cr.savepoint():
            record.write({'company_id': self.b.id})
