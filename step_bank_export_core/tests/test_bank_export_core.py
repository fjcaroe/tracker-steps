import io
import zipfile

import xlrd
from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged
from odoo.tests.common import new_test_user
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from ..hooks import LEGACY_FIELDS, LEGACY_VIEWS, SELECTION_VALUES
from ..models.bank_export_service import clean_rut, whole_pesos


@tagged('post_install', '-at_install')
class BankExportCoreCase(AccountTestInvoicingCommon):
    def payment(self):
        self.env.user.groups_id |= self.env.ref('account.group_validate_bank_account')
        currency = self.env.ref('base.CLP')
        currency.active = True
        journal = self.company_data['default_journal_bank']
        journal.currency_id = currency
        self.partner_a.write({'vat': '12.345.678-5', 'email': 'qa@example.cl'})
        bank = self.env['res.bank'].create({'name': 'Banco formato prueba', 'bic': '012'})
        account = self.env['res.partner.bank'].create({
            'partner_id': self.partner_a.id, 'bank_id': bank.id, 'acc_number': '00123456789',
            'step_security_credit_type': '2', 'allow_out_payment': True})
        payment = self.env['account.payment'].create({
            'payment_type': 'outbound', 'partner_type': 'supplier', 'partner_id': self.partner_a.id,
            'amount': 125000, 'currency_id': currency.id, 'date': fields.Date.today(),
            'journal_id': journal.id, 'payment_method_line_id': journal.outbound_payment_method_line_ids[:1].id,
            'partner_bank_id': account.id, 'memo': 'Prueba formato Community'})
        return payment, account

    @property
    def service(self):
        return self.env['step.bank.export.service']

    def test_two_real_file_formats_preserve_leading_zeroes(self):
        payment, account = self.payment()
        payload = self.service.bancoestado_file(payment, self.env.company)
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            strings = archive.read('xl/sharedStrings.xml').decode()
            sheet = archive.read('xl/worksheets/sheet1.xml').decode()
        self.assertIn('00123456789', strings)
        self.assertIn('MONTO DEL PAGO', strings)
        self.assertIn('<v>125000</v>', sheet)
        payload = self.service.security_file(payment, self.env.company)
        sheet = xlrd.open_workbook(file_contents=payload).sheet_by_index(0)
        self.assertEqual((sheet.nrows, sheet.ncols), (1, 9))
        self.assertEqual(sheet.row_values(0), [2, '123456785', self.partner_a.name,
            '00123456789', 125000, 2, 12, 'qa@example.cl', 'Prueba formato Community'])
        self.assertEqual(sheet.cell_type(0, 3), xlrd.XL_CELL_TEXT)

    def test_export_is_read_only_on_payments_bank_and_ledger(self):
        payment, account = self.payment()
        before_payment = payment.read(['amount', 'state', 'date', 'partner_bank_id', 'write_date', 'move_id'])
        before_bank = account.read(['acc_number', 'allow_out_payment', 'write_date'])
        before_moves = self.env['account.move'].search_count([])
        before_attachments = self.env['ir.attachment'].search_count([])
        self.service.bancoestado_file(payment, self.env.company)
        self.service.security_file(payment, self.env.company)
        self.assertEqual(payment.read(list(before_payment[0].keys() - {'id'})), before_payment)
        self.assertEqual(account.read(list(before_bank[0].keys() - {'id'})), before_bank)
        self.assertEqual(self.env['account.move'].search_count([]), before_moves)
        self.assertEqual(self.env['ir.attachment'].search_count([]), before_attachments)

    def test_untrusted_bank_rejected_by_both_formats(self):
        payment, account = self.payment()
        account.allow_out_payment = False
        for method in (self.service.bancoestado_rows, self.service.security_rows):
            with self.assertRaises(UserError):
                method(payment, self.env.company)

    def test_invalid_rut_and_amount_rejected_without_truncation(self):
        self.assertEqual(clean_rut('CL12.345.678-5'), '123456785')
        for value in ('12.345.678-9', '0-0', '', '12ABC3456785'):
            with self.assertRaises(UserError):
                clean_rut(value)
        for value in (0, -1, 1.5, 'NaN', 'Infinity'):
            with self.assertRaises(UserError):
                whole_pesos(value)

    def test_currency_and_direction_are_checked_by_both_formats(self):
        payment, account = self.payment()
        payment.payment_type = 'inbound'
        for method in (self.service.bancoestado_rows, self.service.security_rows):
            with self.assertRaises(UserError):
                method(payment, self.env.company)
        payment.payment_type = 'outbound'
        payment.currency_id = self.env.ref('base.USD')
        for method in (self.service.bancoestado_rows, self.service.security_rows):
            with self.assertRaises(UserError):
                method(payment, self.env.company)

    def test_empty_selection_does_not_create_an_empty_bank_file(self):
        for method in (self.service.bancoestado_file, self.service.security_file):
            with self.assertRaises(UserError):
                method(self.env['account.payment'], self.env.company)

    def test_existing_master_account_fallback_and_ambiguity(self):
        payment, account = self.payment()
        payment.partner_bank_id = False
        self.assertEqual(self.service.bancoestado_rows(payment, self.env.company)[0][5], account.acc_number)
        self.env['res.partner.bank'].create({'partner_id': self.partner_a.id, 'acc_number': '987654321'})
        with self.assertRaises(UserError):
            self.service.bancoestado_rows(payment, self.env.company)

    def test_beneficiary_account_must_belong_to_original_partner(self):
        payment, account = self.payment()
        # Exercise the service guard independently of payment form domains.
        account.partner_id = self.partner_b
        with self.assertRaises(UserError):
            self.service.security_rows(payment, self.env.company)

    def test_company_is_enforced_even_for_a_caller_allowed_in_both(self):
        payment, account = self.payment()
        other = self.env['res.company'].create({'name': 'Otra empresa formatos Community'})
        with self.assertRaises(UserError):
            self.service.with_context(allowed_company_ids=[self.env.company.id, other.id]).security_rows(payment, other)

    def test_security_optional_columns_and_limits_are_not_silently_truncated(self):
        payment, account = self.payment()
        self.partner_a.email = False
        payment.memo = False
        for code in ('1', '2', '3', '4', '5'):
            account.step_security_credit_type = code
            self.assertEqual(self.service.security_rows(payment, self.env.company)[0][5:],
                             (int(code), 12, '', ''))
        with self.assertRaises(UserError):
            self.service.security_file(payment, self.env.company, 'x' * 101)

    def test_bancoestado_savings_code_and_account_length(self):
        payment, account = self.payment()
        account.step_bancoestado_payment_method = '02'
        self.assertEqual(self.service.bancoestado_rows(payment, self.env.company)[0][4], '02')
        account.bank_id.bic = '037'
        with self.assertRaises(UserError):
            self.service.bancoestado_rows(payment, self.env.company)
        account.step_bancoestado_payment_method = '01'
        account.acc_number = '1' * 18
        with self.assertRaises(UserError):
            self.service.bancoestado_rows(payment, self.env.company)

    def test_normal_user_cannot_bypass_payment_permissions_through_the_service(self):
        payment, account = self.payment()
        user = new_test_user(self.env, login='bank_core_no_accounting', groups='base.group_user')
        for method in ('bancoestado_file', 'security_file'):
            with self.assertRaises(AccessError):
                getattr(self.service.with_user(user), method)(payment.sudo(), self.env.company.sudo())

    def test_fields_and_views_keep_both_namespaces_and_original_form(self):
        for namespace, name in LEGACY_FIELDS.items():
            field_name = 'field_res_partner_bank__' + name
            self.assertEqual(self.env.ref(namespace + '.' + field_name),
                             self.env.ref('step_bank_export_core.' + field_name))
            for value in SELECTION_VALUES[name]:
                selection = 'selection__res_partner_bank__%s__%s' % (name, value)
                self.assertEqual(self.env.ref(namespace + '.' + selection),
                                 self.env.ref('step_bank_export_core.' + selection))
        for namespace, name in LEGACY_VIEWS.items():
            self.assertEqual(self.env.ref(namespace + '.' + name), self.env.ref('step_bank_export_core.' + name))
        arch = self.env['res.partner.bank'].get_view(view_type='form')['arch']
        self.assertEqual(arch.count('name="step_bancoestado_payment_method"'), 1)
        self.assertEqual(arch.count('name="step_security_credit_type"'), 1)
