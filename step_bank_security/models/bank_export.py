"""T104: Excel 97–2003 sin detalles, conforme al adjunto del banco."""
import base64
from decimal import Decimal
import io
import re

import xlwt
from odoo import api, fields, models, _, tools
from odoo.exceptions import UserError, ValidationError


BANK_CODES = {1, 9, 12, 14, 16, 27, 28, 31, 37, 39, 46, 49, 51, 53, 54, 55,
              504, 738, 697, 507, 672, 729, 730, 875, 732, 741, 743, 746, 62}


def whole_pesos(value):
    amount = Decimal(str(value))
    if not amount.is_finite() or amount <= 0 or amount != amount.to_integral_value():
        raise UserError(_('El monto Security debe ser positivo y expresado en pesos enteros.'))
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


class PartnerBank(models.Model):
    _inherit = 'res.partner.bank'

    step_security_credit_type = fields.Selection([
        ('1', 'Cuenta corriente'), ('2', 'Cuenta vista'), ('3', 'Cuenta de ahorro'),
        ('4', 'Vale vista'), ('5', 'Vale vista On-Line')], string='Tipo de abono Security')


class BatchPayment(models.Model):
    _inherit = 'account.batch.payment'

    security_description = fields.Char(string='Glosa Security', copy=False,
                                      help='Opcional, hasta 100 caracteres. Si está vacía se usa la referencia de cada pago.')
    security_export_count = fields.Integer(string='Exportaciones Security', default=0, readonly=True, copy=False)

    @api.constrains('security_description')
    def _check_security_description(self):
        if any(len(batch.security_description or '') > 100 for batch in self):
            raise ValidationError(_('La glosa Security admite hasta 100 caracteres.'))

    def _security_rows(self):
        self.ensure_one()
        self.check_access('write')
        if self.batch_type != 'outbound' or not self.payment_ids:
            raise UserError(_('Seleccione un lote saliente con pagos.'))
        if self.company_id not in self.env.companies:
            raise UserError(_('El lote no pertenece a una empresa activa.'))
        self._check_batch_approval()
        rows = []
        for payment in self.payment_ids.sorted('id'):
            payment.check_access('read')
            if payment.company_id != self.company_id or payment.payment_type != 'outbound':
                raise UserError(_('Todos los pagos deben ser salientes y pertenecer a la empresa del lote.'))
            if payment.state in ('canceled', 'cancel', 'rejected') or payment.currency_id.name != 'CLP':
                raise UserError(_('Security requiere pagos vigentes en pesos chilenos (CLP).'))
            amount = whole_pesos(payment.amount)
            partner = payment.partner_id
            accounts = partner.bank_ids.filtered(lambda bank: not bank.company_id or bank.company_id == self.company_id)
            account = payment.partner_bank_id
            if not account:
                if len(accounts) != 1:
                    raise UserError(_('Seleccione la cuenta beneficiaria del pago; no hay una única cuenta aplicable.'))
                account = accounts
            account.check_access('read')
            if (account.partner_id.commercial_partner_id != partner.commercial_partner_id or
                    (account.company_id and account.company_id != self.company_id)):
                raise UserError(_('La cuenta bancaria no corresponde al beneficiario o a la empresa del lote.'))
            if 'allow_out_payment' in account._fields and not account.allow_out_payment:
                raise UserError(_('La cuenta beneficiaria debe estar autorizada para pagos salientes en Odoo.'))
            if not account.step_security_credit_type or not account.bank_id:
                raise UserError(_('Complete el banco y el tipo de abono Security en la cuenta beneficiaria.'))
            code = account.bank_id.l10n_cl_sbif_code if 'l10n_cl_sbif_code' in account.bank_id._fields else False
            code = code or account.bank_id.bic or ''
            if not re.fullmatch(r'\d+', code) or int(code) not in BANK_CODES:
                raise UserError(_('El banco debe tener un código SBIF admitido por el formato Security del adjunto.'))
            number = re.sub(r'[.\s-]', '', account.acc_number or '')
            if not re.fullmatch(r'\d+', number):
                raise UserError(_('La cuenta beneficiaria debe contener números, sin puntos ni guiones.'))
            email = tools.email_normalize(partner.email) if partner.email else ''
            if (partner.email and not email) or len(email or '') > 50:
                raise UserError(_('El email del beneficiario debe ser válido y tener hasta 50 caracteres.'))
            description = self.security_description or payment.memo or ''
            if len(description) > 100:
                raise UserError(_('La glosa del pago supera los 100 caracteres; complete una glosa Security más breve.'))
            name = partner.name or ''
            if not name.strip():
                raise UserError(_('El beneficiario debe tener nombre.'))
            rows.append((2, clean_rut(partner.vat), name, number, int(amount),
                         int(account.step_security_credit_type), int(code), email or '', description))
        if len(rows) > 65536:
            raise UserError(_('El archivo Excel 97–2003 admite hasta 65536 pagos por nómina.'))
        return rows

    def action_export_security_xls(self):
        rows = self._security_rows()
        stream = io.BytesIO()
        book = xlwt.Workbook(encoding='utf-8')
        sheet = book.add_sheet('Nomina')
        text = xlwt.easyxf(num_format_str='@')
        for row_index, row in enumerate(rows):
            for column, value in enumerate(row):
                sheet.write(row_index, column, value, text if column in (1, 2, 3, 7, 8) else xlwt.Style.default_style)
        book.save(stream)
        safe = re.sub(r'[^A-Za-z0-9_-]', '_', self.name or 'lote')
        attachment = self.env['ir.attachment'].create({
            'name': safe + '_SECURITY.xls', 'type': 'binary', 'mimetype': 'application/vnd.ms-excel',
            'datas': base64.b64encode(stream.getvalue()), 'res_model': self._name, 'res_id': self.id})
        self.security_export_count += 1
        return {'type': 'ir.actions.act_url', 'url': '/web/content/%s?download=true' % attachment.id, 'target': 'self'}
