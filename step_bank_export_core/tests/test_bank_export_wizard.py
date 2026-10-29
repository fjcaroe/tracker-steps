import base64
import io
import zipfile

import xlrd
from odoo import Command
from odoo.exceptions import AccessError, UserError
from odoo.tests import Form, tagged
from odoo.tests.common import new_test_user
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from .test_bank_export_core import make_bank_payment


@tagged('post_install', '-at_install')
class BankExportWizardCase(AccountTestInvoicingCommon):
    def setUp(self):
        super().setUp()
        self.env = self.env(context=dict(self.env.context, no_reset_password=True,
            tracking_disable=True, mail_notrack=True, mail_create_nosubscribe=True,
            mail_notify_force_send=False))
        self.payment, self.bank = make_bank_payment(self)
        self.manager = self.new_actor('bank_wizard_manager')
        self.Wizard = self.env['step.bank.export.wizard'].with_user(self.manager)
        if 'treasury_batch_approval_threshold' in self.env.company._fields:
            self.env.company.treasury_batch_approval_threshold = 0

    def new_actor(self, login, groups='account.group_account_manager,account.group_validate_bank_account,base.group_multi_company'):
        return new_test_user(self.env, login=login, groups=groups,
                             company_id=self.env.company.id, company_ids=[Command.set(self.env.company.ids)])

    def wizard(self):
        return self.Wizard.create({'payment_ids': [Command.set(self.payment.ids)]})

    def test_normal_manager_form_and_download_both_formats_without_payment_writes(self):
        before = self.payment.read(['amount', 'state', 'date', 'write_date', 'move_id', 'partner_bank_id'])
        banks = self.bank.read(['acc_number', 'allow_out_payment', 'write_date'])
        attachment_count = self.env['ir.attachment'].search_count([])
        with Form(self.Wizard.with_context(active_model='account.payment', active_ids=self.payment.ids)) as form:
            self.assertEqual(form.company_id.id, self.env.company.id)
        wizard = form.record
        self.assertFalse(wizard.env.su)
        self.assertEqual(wizard.create_uid, self.manager)
        self.assertEqual(wizard.payment_ids, self.payment)
        for bank_format in ('bancoestado', 'security'):
            wizard.bank_format = bank_format
            action = wizard.action_generate_file()
            self.assertEqual((action['res_model'], action['res_id']), (wizard._name, wizard.id))
            download = wizard.action_download()
            self.assertIn('model=step.bank.export.wizard', download['url'])
            self.assertNotIn('access_token', download['url'])
            binary = self.env['ir.binary'].with_user(self.manager)
            record = binary._find_record(res_model=wizard._name, res_id=wizard.id, field='file_data')
            stream = binary._get_stream_from(record, field_name='file_data', filename_field='file_name')
            payload = base64.b64decode(wizard.file_data)
            self.assertEqual(stream.data, payload)
            if bank_format == 'bancoestado':
                with zipfile.ZipFile(io.BytesIO(payload)) as archive:
                    self.assertIn('00123456789', archive.read('xl/sharedStrings.xml').decode())
            else:
                sheet = xlrd.open_workbook(file_contents=payload).sheet_by_index(0)
                self.assertEqual((sheet.nrows, sheet.ncols), (1, 9))
                self.assertEqual(sheet.cell_value(0, 3), '00123456789')
        self.assertEqual(self.payment.read(list(before[0].keys() - {'id'})), before)
        self.assertEqual(self.bank.read(list(banks[0].keys() - {'id'})), banks)
        self.assertEqual(self.env['ir.attachment'].search_count([]), attachment_count)

    def test_billing_user_cannot_create_or_download_bank_wizard(self):
        user = self.new_actor('bank_wizard_billing', groups='account.group_account_invoice')
        with self.assertRaises(AccessError):
            self.Wizard.with_user(user).create({})
        wizard = self.wizard()
        wizard.action_generate_file()
        with self.assertRaises(AccessError):
            self.env['ir.binary'].with_user(user)._find_record(res_model=wizard._name, res_id=wizard.id, field='file_data')

    def test_other_manager_cannot_read_generate_or_fetch_binary(self):
        wizard = self.wizard()
        wizard.action_generate_file()
        other = self.new_actor('bank_wizard_other_manager')
        with self.assertRaises(AccessError):
            wizard.write({'create_uid': other.id})
        with self.assertRaises(AccessError):
            wizard.with_user(other).read(['file_data'])
        with self.assertRaises(AccessError):
            wizard.with_user(other).action_generate_file()
        with self.assertRaises(AccessError):
            self.env['ir.binary'].with_user(other)._find_record(res_model=wizard._name, res_id=wizard.id, field='file_data')

    def test_foreign_company_and_inactive_company_are_rejected(self):
        other = self.env['res.company'].create({'name': 'Otra empresa archivo privado'})
        self.manager.company_ids |= other
        with self.assertRaises(UserError):
            self.Wizard.with_context(allowed_company_ids=[self.env.company.id, other.id]).create({
                'company_id': other.id, 'payment_ids': [Command.set(self.payment.ids)]})
        with self.assertRaises(UserError):
            self.Wizard.with_context(allowed_company_ids=self.env.company.ids).create({'company_id': other.id})

    def test_payment_hidden_by_native_record_rules_is_rejected(self):
        wizard = self.wizard()
        self.env['ir.rule'].create({'name': 'Pago oculto de prueba bancaria',
            'model_id': self.env['ir.model']._get_id('account.payment'),
            'domain_force': repr([('id', '!=', self.payment.id)]),
            'perm_read': True, 'perm_write': False, 'perm_create': False, 'perm_unlink': False})
        with self.assertRaises(AccessError):
            wizard.action_generate_file()
        with self.assertRaises(AccessError):
            self.wizard()

    def test_generated_file_cannot_be_injected_or_modified(self):
        with self.assertRaises(UserError):
            self.Wizard.create({'file_data': base64.b64encode(b'forged')})
        wizard = self.Wizard.with_context(default_file_data=base64.b64encode(b'forged')).create({})
        self.assertFalse(wizard.file_data)
        wizard = self.wizard()
        wizard.action_generate_file()
        original = wizard.file_data
        with self.assertRaises(UserError):
            wizard.write({'file_data': base64.b64encode(b'forged')})
        self.assertEqual(wizard.file_data, original)

    def test_editing_selection_invalidates_private_file(self):
        wizard = self.wizard()
        wizard.action_generate_file()
        self.assertTrue(wizard.file_data)
        wizard.bank_format = 'security'
        self.assertFalse(wizard.file_data)
        self.assertFalse(wizard.file_name)
        with self.assertRaises(UserError):
            wizard.action_download()

    def test_without_file_download_requires_generation(self):
        wizard = self.wizard()
        with self.assertRaises(UserError):
            wizard.action_download()

    def test_original_treasury_approver_cannot_be_bypassed(self):
        if 'treasury_batch_approval_threshold' not in self.env.company._fields:
            self.skipTest('The Enterprise batch approval policy is only present on the native reference')
        other = self.new_actor('bank_wizard_approver')
        self.env.company.write({'treasury_batch_approval_threshold': 100, 'treasury_batch_approver_id': other.id})
        wizard = self.wizard()
        with self.assertRaises(UserError):
            wizard.action_generate_file()
        self.env.company.treasury_batch_approver_id = self.manager
        wizard.action_generate_file()
        self.assertTrue(wizard.file_data)

    def test_entrypoint_menu_action_form_and_bound_payment_ids(self):
        action = self.env.ref('step_bank_export_core.action_bank_export_wizard')
        self.assertEqual(action.binding_model_id.model, 'account.payment')
        self.assertEqual(action.groups_id, self.env.ref('account.group_account_manager'))
        menu = self.env.ref('step_bank_export_core.menu_bank_export_wizard')
        self.assertEqual(menu.action, action)
        self.assertEqual(menu.groups_id, self.env.ref('account.group_account_manager'))
        view = self.env.ref('step_bank_export_core.view_bank_export_wizard_form')
        arch = self.Wizard.get_view(view_id=view.id, view_type='form')['arch']
        for name in ('payment_ids', 'bank_format', 'file_data', 'action_generate_file', 'action_download'):
            self.assertIn('name="' + name + '"', arch)
        values = self.Wizard.with_context(active_model='res.partner', active_ids=self.partner_a.ids).default_get(['payment_ids'])
        self.assertFalse(values.get('payment_ids'))

    def test_losing_accounting_role_revokes_binary_download(self):
        wizard = self.wizard()
        wizard.action_generate_file()
        self.manager.groups_id = [Command.set(self.env.ref('base.group_user').ids)]
        with self.assertRaises(AccessError):
            self.env['ir.binary'].with_user(self.manager)._find_record(res_model=wizard._name, res_id=wizard.id, field='file_data')
