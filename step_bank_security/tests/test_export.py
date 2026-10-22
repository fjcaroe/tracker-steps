import base64
import xlrd
from odoo import Command, fields
from odoo.tests import tagged
from odoo.tests.common import new_test_user
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.exceptions import UserError, AccessError
from ..models.bank_export import clean_rut


@tagged('post_install', '-at_install')
class SecurityExportCase(AccountTestInvoicingCommon):
    def make_batch(self):
        self.env.company.treasury_batch_approval_threshold = 0
        journal = self.company_data['default_journal_bank']
        currency = self.env.ref('base.CLP')
        journal.currency_id = currency
        partner = self.partner_a
        partner.write({'vat': '12.345.678-5', 'email': 'qa@example.cl'})
        bank = self.env['res.bank'].create({'name': 'QA Security', 'bic': '049'})
        values = {'partner_id': partner.id, 'bank_id': bank.id, 'acc_number': '00123456789',
                  'step_security_credit_type': '2'}
        if 'allow_out_payment' in self.env['res.partner.bank']._fields:
            values['allow_out_payment'] = True
        account = self.env['res.partner.bank'].create(values)
        payment = self.env['account.payment'].create({
            'payment_type': 'outbound', 'partner_type': 'supplier', 'partner_id': partner.id,
            'amount': 125000, 'currency_id': currency.id, 'date': fields.Date.today(),
            'journal_id': journal.id, 'payment_method_line_id': journal.outbound_payment_method_line_ids[:1].id,
            'partner_bank_id': account.id, 'memo': 'QA pago remuneraciones'})
        batch = self.env['account.batch.payment'].create({
            'batch_type': 'outbound', 'date': fields.Date.today(), 'journal_id': journal.id,
            'payment_ids': [Command.set(payment.ids)]})
        return batch, payment, account

    def test_real_biff8_nine_columns_no_header_and_text_account(self):
        batch, payment, account = self.make_batch()
        action = batch.action_export_security_xls()
        attachment = self.env['ir.attachment'].browse(int(action['url'].split('/web/content/')[1].split('?')[0]))
        payload = base64.b64decode(attachment.datas)
        self.assertTrue(payload.startswith(bytes.fromhex('d0cf11e0a1b11ae1')))
        sheet = xlrd.open_workbook(file_contents=payload).sheet_by_index(0)
        self.assertEqual((sheet.nrows, sheet.ncols), (1, 9))
        self.assertEqual(sheet.row_values(0), [2, '123456785', self.partner_a.name, '00123456789',
                         125000, 2, 49, 'qa@example.cl', 'QA pago remuneraciones'])
        self.assertEqual(sheet.cell_type(0, 3), xlrd.XL_CELL_TEXT)
        self.assertEqual(attachment.mimetype, 'application/vnd.ms-excel')
        self.assertEqual((attachment.res_model, attachment.res_id), ('account.batch.payment', batch.id))
        self.assertFalse(attachment.public)
        self.assertEqual(batch.security_export_count, 1)

    def test_all_five_credit_types_and_optional_columns(self):
        batch, payment, account = self.make_batch()
        self.partner_a.email = False
        payment.memo = False
        for code in ('1', '2', '3', '4', '5'):
            account.step_security_credit_type = code
            row = batch._security_rows()[0]
            self.assertEqual(row[5], int(code))
            self.assertEqual(row[7:], ('', ''))

    def test_rejects_invalid_rut_currency_fraction_and_missing_credit_type(self):
        self.assertEqual(clean_rut('CL12.345.678-5'), '123456785')
        with self.assertRaises(UserError):
            clean_rut('12.345.678-9')
        batch, payment, account = self.make_batch()
        account.step_security_credit_type = False
        with self.assertRaises(UserError):
            batch._security_rows()
        account.step_security_credit_type = '1'
        payment.amount = 10.5
        with self.assertRaises(UserError):
            batch._security_rows()
        payment.amount = 100
        payment.currency_id = self.env.ref('base.USD')
        with self.assertRaises(UserError):
            batch._security_rows()

    def test_uses_existing_sbif_and_rejects_unknown_bank(self):
        batch, payment, account = self.make_batch()
        account.bank_id.bic = 'SWIFT'
        if 'l10n_cl_sbif_code' in account.bank_id._fields:
            account.bank_id.l10n_cl_sbif_code = '504'
            self.assertEqual(batch._security_rows()[0][6], 504)
            account.bank_id.l10n_cl_sbif_code = False
        with self.assertRaises(UserError):
            batch._security_rows()

    def test_email_glosa_and_account_are_not_silently_truncated(self):
        batch, payment, account = self.make_batch()
        self.partner_a.email = 'a' * 45 + '@example.cl'
        with self.assertRaises(UserError):
            batch._security_rows()
        self.partner_a.email = False
        payment.memo = 'x' * 101
        with self.assertRaises(UserError):
            batch._security_rows()
        batch.security_description = 'Nómina octubre'
        self.assertEqual(batch._security_rows()[0][8], 'Nómina octubre')
        account.acc_number = 'ABC-123'
        with self.assertRaises(UserError):
            batch._security_rows()

    def test_ambiguous_account_and_batch_approval_are_enforced(self):
        batch, payment, account = self.make_batch()
        payment.partner_bank_id = False
        self.env['res.partner.bank'].create({'partner_id': self.partner_a.id, 'acc_number': '9999999'})
        with self.assertRaises(UserError):
            batch._security_rows()
        payment.partner_bank_id = account
        batch.company_id.treasury_batch_approval_threshold = 100
        with self.assertRaises(UserError):
            batch._security_rows()

    def test_user_without_batch_access_cannot_generate_file(self):
        batch, payment, account = self.make_batch()
        user = new_test_user(self.env, login='qa_t104_no_accounting', groups='base.group_user')
        with self.assertRaises(AccessError):
            batch.with_user(user).action_export_security_xls()
