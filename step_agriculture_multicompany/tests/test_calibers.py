from lxml import etree
from odoo import Command
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import TransactionCase, Form, tagged, new_test_user


@tagged('post_install', '-at_install')
class TestSharedCalibers(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.a = cls.env.company
        cls.b = cls.env['res.company'].create({'name': 'QA T200 branch', 'parent_id': cls.a.id})
        cls.c = cls.env['res.company'].create({'name': 'QA T200 foreign'})
        cls.editor = new_test_user(cls.env, login='qa-t200-editor',
            groups='base.group_user,base.group_erp_manager,base.group_multi_company,stock.group_stock_manager,step_management_costs.group_management_manager',
            company_id=cls.a.id, company_ids=[Command.set((cls.a | cls.b).ids)])
        cls.operator = new_test_user(cls.env, login='qa-t200-operator',
            groups='base.group_user,stock.group_stock_manager,step_management_costs.group_management_readonly',
            company_id=cls.b.id, company_ids=[Command.set(cls.b.ids)])
        cls.group = cls.env['step.management.caliber.group'].create({
            'code': 'QA-T200', 'name': 'QA T200 group', 'company_id': cls.a.id})
        cls.caliber = cls.env['step.management.fruit.caliber'].create({
            'code': 'QA-T200', 'name': 'QA T200 caliber', 'group_id': cls.group.id, 'company_id': cls.a.id})

    def share(self):
        self.caliber.with_user(self.editor).write({'company_ids': [Command.link(self.b.id)]})

    def test_share_existing_record_and_group(self):
        original = self.caliber.id
        self.share()
        self.assertEqual(self.caliber.id, original)
        self.assertEqual(self.caliber.company_id, self.a)
        self.assertEqual(self.group.company_id, self.a)
        for record in (self.caliber, self.group):
            self.assertEqual(record.company_ids, self.a | self.b)
            scoped = record.with_user(self.operator).with_context(allowed_company_ids=self.b.ids)
            scoped.read(['name'])
            self.assertEqual(scoped.search([('id', '=', record.id)]).ids, record.ids)
        data = self.caliber.with_user(self.operator).web_read({
            'name': {}, 'group_id': {'fields': {'display_name': {}}}})
        self.assertEqual(data[0]['group_id']['id'], self.group.id)

    def test_save_same_caliber_on_branch_tag_and_import_selector(self):
        self.share()
        scoped = self.env(user=self.operator, context={'allowed_company_ids': self.b.ids})
        self.assertIn(self.caliber.id, scoped['step.external.fruit.reception.import']._masters(
            'step.management.fruit.caliber').ids)
        tag = scoped['stock.quant.package'].create({
            'name': 'QA T200 branch tag', 'company_id': self.b.id, 'is_fruit_tag': True,
            'step_tag_kind': 'E', 'fruit_caliber_id': self.caliber.id})
        self.assertEqual(tag.fruit_caliber_id, self.caliber)
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self.caliber.write({'company_ids': [Command.set(self.a.ids)]})

    def test_foreign_tag_and_assignment_rejected(self):
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self.env['stock.quant.package'].with_company(self.c).create({
                'name': 'QA T200 foreign tag', 'company_id': self.c.id,
                'is_fruit_tag': True, 'step_tag_kind': 'E', 'fruit_caliber_id': self.caliber.id})
        with self.assertRaises(AccessError), self.cr.savepoint():
            self.caliber.with_user(self.editor).write({'company_ids': [Command.link(self.c.id)]})
        self.assertNotIn(self.c, self.group.company_ids)

    def test_group_cannot_lose_branch_with_assigned_caliber(self):
        self.share()
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self.group.write({'company_ids': [Command.set(self.a.ids)]})

    def test_overlap_and_origin_are_preserved(self):
        group = self.env['step.management.caliber.group'].with_company(self.b).create({
            'code': 'QA-T200-B', 'name': 'QA branch group'})
        self.env['step.management.fruit.caliber'].with_company(self.b).create({
            'code': self.caliber.code, 'name': 'QA duplicate', 'group_id': group.id})
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self.share()
        for values in ({'company_id': self.b.id}, {'company_ids': [Command.clear()]}):
            with self.assertRaises(ValidationError), self.cr.savepoint():
                self.caliber.write(values)

    def test_form_menu_and_operator_visibility(self):
        record = self.caliber.with_user(self.editor).with_context(allowed_company_ids=(self.a | self.b).ids)
        with Form(record, view='step_agriculture_multicompany.caliber_form') as form:
            form.company_ids.add(self.b)
        self.assertEqual(self.caliber.company_ids, self.a | self.b)
        menu = self.env.ref('step_packing_operations.menu_packing_config_fruit_caliber')
        self.assertEqual(menu.action, self.env.ref('step_management_costs.action_fruit_caliber'))
        for kind in ('list', 'form'):
            arch = etree.fromstring(record.get_view(view_type=kind)['arch'])
            self.assertTrue(arch.xpath("//field[@name='company_ids'][@widget='many2many_tags']"))
            operator_arch = etree.fromstring(record.with_user(self.operator).get_view(view_type=kind)['arch'])
            self.assertFalse(operator_arch.xpath("//field[@name='company_ids']"))

    def test_migration_backfills_only_original_memberships(self):
        from odoo.addons.step_agriculture_multicompany.hooks import post_init_hook
        self.env.flush_all()
        self.cr.execute('DELETE FROM step_fruit_caliber_company_rel WHERE master_id=%s', [self.caliber.id])
        self.caliber.invalidate_recordset(['company_ids'])
        post_init_hook(self.env)
        self.assertEqual(self.caliber.company_ids, self.a)
        self.share()
        post_init_hook(self.env)
        self.assertEqual(self.caliber.company_ids, self.a | self.b)
