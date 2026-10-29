"""Stateless bank layouts using real Community account.payment records.

No payments are created, posted, reconciled or changed while rendering. Batch
approval, attachments and export counters remain the responsibility of the
batch adapter. The service grants no additional access to financial records.
"""
from decimal import Decimal
import io
import re

import xlwt
import xlsxwriter

from odoo import _, api, models, tools
from odoo.exceptions import UserError


BANK_CODES = {1, 9, 12, 14, 16, 27, 28, 31, 37, 39, 46, 49, 51, 53, 54, 55,
              504, 738, 697, 507, 672, 729, 730, 875, 732, 741, 743, 746, 62}


def whole_pesos(value):
    amount = Decimal(str(value))
    if not amount.is_finite() or amount <= 0 or amount != amount.to_integral_value():
        raise UserError(_('El monto bancario debe ser positivo y expresado en pesos enteros.'))
    return int(amount)


def clean_rut(value):
    value = re.sub(r'^CL', '', (value or '').strip(), flags=re.I)
    value = re.sub(r'[.\s-]', '', value).upper()
    if not re.fullmatch(r'\d{1,8}[0-9K]', value) or not int(value[:-1]):
        raise UserError(_('El beneficiario debe tener un RUT chileno válido.'))
    total = sum(int(digit) * (2 + index % 6) for index, digit in enumerate(reversed(value[:-1])))
    remainder = 11 - total % 11
    expected = '0' if remainder == 11 else 'K' if remainder == 10 else str(remainder)
    if value[-1] != expected:
        raise UserError(_('El dígito verificador del RUT del beneficiario no es válido.'))
    return value


class BankExportService(models.AbstractModel):
    _name = 'step.bank.export.service'
    _description = 'Formatos bancarios sobre pagos originales'

    @api.model
    def _payments(self, payments, company):
        if payments._name != 'account.payment' or company._name != 'res.company':
            raise UserError(_('Seleccione pagos contables y una empresa.'))
        # The service's caller controls access even when a Python consumer
        # accidentally passes records previously browsed with sudo().
        payments = self.env['account.payment'].browse(payments.ids)
        company = self.env['res.company'].browse(company.ids)
        company.ensure_one()
        company.check_access('read')
        if company not in self.env.companies:
            raise UserError(_('La empresa de los pagos debe estar activa.'))
        if not payments:
            raise UserError(_('Seleccione al menos un pago saliente.'))
        payments.check_access('read')
        for payment in payments:
            if payment.company_id != company or payment.payment_type != 'outbound':
                raise UserError(_('Todos los pagos deben ser salientes y pertenecer a la empresa.'))
            if payment.state in ('canceled', 'cancel', 'rejected') or payment.currency_id.name != 'CLP':
                raise UserError(_('Los formatos chilenos requieren pagos vigentes en pesos chilenos (CLP).'))
            whole_pesos(payment.amount)
        return payments

    @api.model
    def _beneficiary(self, payment, company):
        partner = payment.partner_id
        partner.check_access('read')
        if not partner or not (partner.name or '').strip():
            raise UserError(_('El pago debe tener un beneficiario con nombre.'))
        accounts = partner.bank_ids.filtered(lambda bank: not bank.company_id or bank.company_id == company)
        account = payment.partner_bank_id
        if not account:
            if len(accounts) != 1:
                raise UserError(_('Seleccione la cuenta beneficiaria del pago; no hay una única cuenta aplicable.'))
            account = accounts
        account.check_access('read')
        if account.partner_id.commercial_partner_id != partner.commercial_partner_id or (
                account.company_id and account.company_id != company):
            raise UserError(_('La cuenta bancaria no corresponde al beneficiario o a la empresa.'))
        if 'allow_out_payment' in account._fields and not account.allow_out_payment:
            raise UserError(_('La cuenta beneficiaria debe estar autorizada para pagos salientes en Odoo.'))
        if not account.bank_id:
            raise UserError(_('La cuenta beneficiaria debe tener un banco asociado.'))
        email = tools.email_normalize(partner.email) if partner.email else ''
        if partner.email and not email:
            raise UserError(_('El email del beneficiario debe ser válido.'))
        number = re.sub(r'[.\s-]', '', account.acc_number or '')
        if not re.fullmatch(r'\d+', number):
            raise UserError(_('La cuenta beneficiaria debe contener números, sin puntos ni guiones.'))
        return partner, account, clean_rut(partner.vat), number, email or ''

    @api.model
    def bancoestado_rows(self, payments, company):
        rows = []
        for payment in self._payments(payments, company).sorted(key=lambda p: (p.partner_id.name or '', p.id)):
            partner, account, rut, number, email = self._beneficiary(payment, company)
            code = account.bank_id.bic or ''
            if not re.fullmatch(r'\d{3}', code):
                raise UserError(_('El banco debe tener un código BancoEstado/SBIF de tres dígitos en BIC/SWIFT.'))
            method = account.step_bancoestado_payment_method or '01'
            if len(number) > 17:
                raise UserError(_('La cuenta BancoEstado admite un máximo de 17 dígitos.'))
            if method == '02' and code != '012':
                raise UserError(_('La forma de pago 02 sólo se permite para cuentas BancoEstado, código 012.'))
            rows.append((rut, partner.name, email, code, method, number, whole_pesos(payment.amount)))
        return rows

    @api.model
    def security_rows(self, payments, company, description=''):
        if len(description or '') > 100:
            raise UserError(_('La glosa Security admite hasta 100 caracteres.'))
        rows = []
        for payment in self._payments(payments, company).sorted('id'):
            partner, account, rut, number, email = self._beneficiary(payment, company)
            code = (account.bank_id.l10n_cl_sbif_code if 'l10n_cl_sbif_code' in account.bank_id._fields else False)
            code = code or account.bank_id.bic or ''
            if not re.fullmatch(r'\d+', code) or int(code) not in BANK_CODES:
                raise UserError(_('El banco debe tener un código SBIF admitido por el formato Security.'))
            if not account.step_security_credit_type:
                raise UserError(_('Complete el tipo de abono Security en la cuenta beneficiaria.'))
            text = description or payment.memo or ''
            if len(email) > 50 or len(text) > 100:
                raise UserError(_('El email admite hasta 50 caracteres y la glosa hasta 100.'))
            rows.append((2, rut, partner.name, number, whole_pesos(payment.amount),
                         int(account.step_security_credit_type), int(code), email, text))
        if len(rows) > 65536:
            raise UserError(_('El archivo Excel 97–2003 admite hasta 65536 pagos por nómina.'))
        return rows

    @api.model
    def bancoestado_file(self, payments, company):
        stream = io.BytesIO()
        workbook = xlsxwriter.Workbook(stream, {'in_memory': True})
        sheet = workbook.add_worksheet('Pago 7 Columnas')
        header = workbook.add_format({'bold': True, 'bg_color': '#D9EAF7', 'border': 1})
        text_format = workbook.add_format({'num_format': '@'})
        amount_format = workbook.add_format({'num_format': '#,##0.00'})
        titles = ['RUT', 'NOMBRES Y APELLIDOS O RAZÓN SOCIAL', 'EMAIL', 'BANCO',
                  'FORMA DE PAGO', 'N° DE CUENTA', 'MONTO DEL PAGO']
        for column, title in enumerate(titles):
            sheet.write(0, column, title, header)
        for row_index, values in enumerate(self.bancoestado_rows(payments, company), start=1):
            for column, value in enumerate(values):
                if column == 6:
                    sheet.write_number(row_index, column, value, amount_format)
                else:
                    sheet.write_string(row_index, column, str(value), text_format)
        sheet.set_column(0, 0, 14)
        sheet.set_column(1, 1, 42)
        sheet.set_column(2, 2, 32)
        sheet.set_column(3, 5, 18)
        sheet.set_column(6, 6, 20)
        sheet.freeze_panes(1, 0)
        workbook.close()
        return stream.getvalue()

    @api.model
    def security_file(self, payments, company, description=''):
        stream = io.BytesIO()
        book = xlwt.Workbook(encoding='utf-8')
        sheet = book.add_sheet('Nomina')
        text = xlwt.easyxf(num_format_str='@')
        for row_index, row in enumerate(self.security_rows(payments, company, description)):
            for column, value in enumerate(row):
                sheet.write(row_index, column, value, text if column in (1, 2, 3, 7, 8) else xlwt.Style.default_style)
        book.save(stream)
        return stream.getvalue()
