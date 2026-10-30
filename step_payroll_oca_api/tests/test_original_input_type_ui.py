"""Actual Community input-type forms/actions, normal actors and no master seeds."""
from unittest import TestCase
from unittest.mock import patch

from lxml import etree

from odoo import api, Command
from odoo.exceptions import AccessError
from odoo.tests import Form, TransactionCase, tagged


@tagged('post_install', '-at_install')
class OriginalInputTypeUICase(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({'name': 'Private input-type UI company',
            'country_id': cls.env.ref('base.cl').id})
        cls.manager = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Private input-type UI manager', 'login': 'private-input-type-ui-manager',
            'company_id': cls.company.id, 'company_ids': [Command.set(cls.company.ids)],
            'groups_id': [Command.set([cls.env.ref('base.group_user').id,
                cls.env.ref('payroll.group_payroll_manager').id])]})
        cls.scope = api.Environment(cls.env.cr, cls.manager.id,
            dict(cls.env.context, allowed_company_ids=cls.company.ids, lang='en_US'), su=False)
        cls.model = cls.scope['hr.payslip.input.type']

    def _stored(self):
        self.env.flush_all()
        self.env.cr.execute('SELECT id,to_jsonb(t) FROM hr_payslip_input_type t ORDER BY id')
        return dict(self.env.cr.fetchall())

    def _record(self):
        return self.model.create({'name': 'Private real input type UI record', 'code': 'PRIVATE_INPUT_UI',
            'country_id': self.company.country_id.id})

    def test_manager_real_form_action_and_menu_preserve_existing_master_rows(self):
        self.assertFalse(self.scope.su)
        before = self._stored()
        view = self.scope.ref('step_payroll_oca_api.original_input_type_form')
        model_view = self.model.get_view(view_id=view.id, view_type='form')
        architecture = etree.fromstring(model_view['arch'].encode())
        for name in ('name', 'code', 'active', 'country_id', 'struct_ids', 'is_quantity',
                'default_no_end_date', 'available_in_attachments'):
            self.assertIn(name, self.model._fields)
            self.assertTrue(architecture.xpath(".//field[@name='%s']" % name))
        editor = Form(self.model, view='step_payroll_oca_api.original_input_type_form')
        editor.name = 'Private real Community form input'
        editor.code = 'PRIVATE_INPUT_FORM'
        editor.country_id = self.scope.ref('base.cl')
        for name in ('is_quantity', 'default_no_end_date', 'available_in_attachments'):
            with TestCase.assertRaises(self, AssertionError):
                setattr(editor, name, True)
        record = editor.save()
        self.assertEqual(record.env.uid, self.scope.uid)
        self.assertEqual(record.country_id, self.scope.ref('base.cl'))
        self.assertEqual({ident: row for ident, row in self._stored().items() if ident in before}, before)
        self.assertEqual(set(self._stored()) - set(before), {record.id})
        action = self.scope['ir.actions.actions']._for_xml_id('step_payroll_oca_api.original_input_type_action')
        self.assertEqual(action['res_model'], self.model._name)
        self.assertEqual(action['views'], [
            (self.scope.ref('step_payroll_oca_api.original_input_type_list').id, 'list'), (view.id, 'form')])
        menu = self.scope.ref('step_payroll_oca_api.original_input_type_menu')
        self.assertEqual(menu.parent_id, self.scope.ref('payroll.payroll_menu_configuration'))
        self.assertEqual(menu.groups_id, self.scope.ref('payroll.group_payroll_manager'))
        self.assertIn(menu.id, self.scope['ir.ui.menu']._visible_menu_ids())

    def test_input_type_ui_grants_no_access_to_internal_or_foreign_country_records(self):
        record = self._record()
        actor = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Private input-type UI internal', 'login': 'private-input-type-ui-internal',
            'company_id': self.company.id, 'company_ids': [Command.set(self.company.ids)],
            'groups_id': [Command.set(self.env.ref('base.group_user').ids)]})
        before = self._stored()
        with TestCase.assertRaises(self, AccessError):
            record.with_user(actor).check_access('read')
        with TestCase.assertRaises(self, AccessError):
            self.model.with_user(actor).create({'name': 'Forbidden UI type', 'code': 'PRIVATE_UI_DENIED'})
        menu = self.scope.ref('step_payroll_oca_api.original_input_type_menu')
        self.assertNotIn(menu.id, self.scope['ir.ui.menu'].with_user(actor)._visible_menu_ids())
        self.assertEqual(self._stored(), before)
        foreign = self.env['hr.payslip.input.type'].create({'name': 'Private foreign UI type',
            'code': 'PRIVATE_UI_FOREIGN', 'country_id': self.env.ref('base.fr').id})
        before = self._stored()
        with TestCase.assertRaises(self, AccessError):
            foreign.with_env(self.scope).read(['name', 'code'])
        self.assertEqual(self._stored(), before)

    def test_field_group_restriction_uses_actual_uid_even_after_warm_manager_cache(self):
        record = self._record()
        record.read(['code'])
        before = self._stored()
        with patch.object(self.model._fields['code'], 'groups', 'base.group_system'):
            self.env.registry.clear_cache()
            try:
                result = self.model.get_view(view_id=self.scope.ref('step_payroll_oca_api.original_input_type_form').id,
                    view_type='form')
                self.assertFalse(etree.fromstring(result['arch'].encode()).xpath(".//field[@name='code']"))
                with TestCase.assertRaises(self, AccessError):
                    record.read(['code'])
                with TestCase.assertRaises(self, AccessError):
                    record.write({'code': 'PRIVATE_UI_FORBIDDEN_FIELD'})
            finally:
                self.env.registry.clear_cache()
        self.assertEqual(self._stored(), before)
