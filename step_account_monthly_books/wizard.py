import base64
from datetime import date
from io import BytesIO

from dateutil.relativedelta import relativedelta
from xlsxwriter import Workbook
from xlsxwriter.utility import xl_range

from odoo import _, fields, models
from odoo.exceptions import UserError


MONTHS = (
    'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
    'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre',
)
BOOKS = [('sales', 'Libro de ventas'), ('purchases', 'Libro de compras'), ('fees', 'Libro de honorarios')]
FEE_CODES = ('70', '71')
IDENTITY = ('Correlativo', 'Tipo de Doc', 'Número de Documento', 'RUT Nº', 'Contacto')
DATES = ('Fecha de factura', 'Fecha de vencimiento')
COLUMNS = {
    'sales': IDENTITY + DATES + (
        'Neto', 'IVA', 'Total', 'IVA Retenido', 'IVA no retenido', 'Total recibir', 'Estado',
    ),
    'purchases': IDENTITY + ('Tipo de compra',) + DATES + (
        'Valor exento', 'Neto', 'I. Específico', 'IVA', 'Total', 'IVA retenido',
        'IVA no retenido', 'Total a pagar', 'Estado',
    ),
    'fees': IDENTITY + DATES + ('Valor exento', 'Total', 'Impuesto', 'Total a pagar', 'Estado'),
}


class AccountMonthlyBook(models.TransientModel):
    _name = 'step.account.monthly.book'
    _description = 'Libros mensuales de Contabilidad'

    month = fields.Selection(
        [(str(index), month) for index, month in enumerate(MONTHS, 1)],
        string='Mes', required=True, default=lambda self: str(fields.Date.context_today(self).month),
    )
    year = fields.Integer(string='Año', required=True, default=lambda self: fields.Date.context_today(self).year)
    book = fields.Selection(BOOKS, string='Libro', required=True, default='sales')
    file_data = fields.Binary(attachment=False, readonly=True)

    def _period(self):
        self.ensure_one()
        if not 1 <= self.year < 9999:
            raise UserError(_('Indique un año válido.'))
        start = date(self.year, int(self.month), 1)
        return start, start + relativedelta(months=1)

    def _moves(self):
        start, end = self._period()
        sale = self.book == 'sales'
        document = 'l10n_latam_document_type_id'
        return self.env['account.move'].search([
            ('company_id', '=', self.env.company.id),
            ('state', '=', 'posted'),
            ('move_type', 'in', ('out_invoice', 'out_refund') if sale else ('in_invoice', 'in_refund')),
            ('invoice_date', '>=', start),
            ('invoice_date', '<', end),
            (document + '.country_id', '=', self.env.ref('base.cl').id),
            (document + '.internal_type', 'in', ('invoice', 'invoice_in', 'credit_note', 'debit_note')),
            (document + '.code', 'in' if self.book == 'fees' else 'not in', FEE_CODES),
        ], order='invoice_date, name, id')

    def _amounts(self, move):
        # Work from posted balances in company currency, including export invoices in another currency.
        sign = -1 if move.is_sale_document() else 1
        amounts = dict(exempt=0.0, net=0.0, vat=0.0, specific=0.0, withheld=0.0)
        for line in move.line_ids:
            tax = line.tax_line_id
            code = tax.l10n_cl_sii_code
            amount = sign * line.balance
            if tax:
                if self.book == 'fees' or (code in (15, 16) and tax.amount < 0):
                    amounts['withheld'] -= amount
                elif code == 14:
                    amounts['vat'] += amount
                else:
                    amounts['specific'] += amount
            elif line.display_type == 'product':
                tax_codes = line.tax_ids.flatten_taxes_hierarchy().mapped('l10n_cl_sii_code')
                taxable = 14 in tax_codes or (self.book == 'fees' and 15 in tax_codes)
                amounts['net' if taxable else 'exempt'] += amount
        currency = move.company_currency_id
        payable = currency.round(-sign * move.amount_total_signed)
        withheld = currency.round(amounts['withheld'])
        amounts.update(
            payable=payable,
            gross=currency.round(payable + withheld),
            remaining_vat=currency.round(amounts['vat'] - withheld) if withheld else None,
        )
        return amounts

    def _row(self, index, move):
        amounts = self._amounts(move)
        document = move.l10n_latam_document_type_id
        common = (index, int(document.code) if document.code.isdecimal() else document.code,
                  move.l10n_latam_document_number or move.ref or move.name,
                  move.partner_id.vat or move.commercial_partner_id.vat or '',
                  move.partner_id.name or '')
        dates = (move.invoice_date, move.invoice_date_due)
        if self.book == 'sales':
            values = (amounts['net'] + amounts['exempt'], amounts['vat'], amounts['gross'],
                      amounts['withheld'], amounts['remaining_vat'], amounts['payable'])
        elif self.book == 'purchases':
            common += ('',)
            values = (amounts['exempt'], amounts['net'], amounts['specific'], amounts['vat'], amounts['gross'],
                      amounts['withheld'], amounts['remaining_vat'], amounts['payable'])
        else:
            values = (amounts['exempt'], amounts['gross'], amounts['withheld'], amounts['payable'])
        return common + dates + values + (_('Registrado'),)

    def _xlsx(self):
        self.ensure_one()
        start, _end = self._period()
        company = self.env.company
        title = dict(BOOKS)[self.book]
        headers = COLUMNS[self.book]
        first_amount = len(IDENTITY) + len(DATES) + (self.book == 'purchases')
        last_amount = len(headers) - 2
        with BytesIO() as output:
            with Workbook(output, {'in_memory': True, 'strings_to_formulas': False, 'strings_to_urls': False}) as book:
                sheet = book.add_worksheet(title)
                heading = book.add_format({'bold': True, 'font_color': '#FFFFFF', 'bg_color': '#27455F'})
                date_format = book.add_format({'num_format': 'dd/mm/yyyy'})
                decimals = company.currency_id.decimal_places
                number = '#,##0' + ('.' + '0' * decimals if decimals else '')
                money = book.add_format({'num_format': number})
                total = book.add_format({'bold': True, 'num_format': number, 'top': 1})
                sheet.write_row(0, 0, ('EMPRESA', company.name))
                sheet.merge_range(0, 3, 0, 5, title.upper(), heading)
                sheet.write_row(0, 6, ('MES', start.strftime('%m/%Y')))
                sheet.write_row(1, 0, ('RUT', company.vat or ''))
                sheet.write_row(2, 0, ('Moneda', company.currency_id.name))
                sheet.write_row(4, 0, headers, heading)
                sheet.set_column(0, 1, 14)
                sheet.set_column(2, 3, 23)
                sheet.set_column(4, 4, 34)
                sheet.set_column(5, len(headers) - 1, 20)
                sheet.freeze_panes(5, 0)
                row_number = 5
                totals = dict.fromkeys(range(first_amount, last_amount + 1), 0.0)
                for index, move in enumerate(self._moves(), 1):
                    row = self._row(index, move)
                    for column, value in enumerate(row):
                        if first_amount <= column <= last_amount:
                            if value is not None:
                                sheet.write_number(row_number, column, value, money)
                                totals[column] += value
                        elif first_amount - 2 <= column < first_amount and value:
                            sheet.write_datetime(row_number, column, value, date_format)
                        elif value is not False:
                            sheet.write(row_number, column, value)
                    row_number += 1
                sheet.autofilter(4, 0, max(5, row_number - 1), len(headers) - 1)
                sheet.write(row_number, 1, _('Totalizar'), total)
                for column, value in totals.items():
                    if row_number > 5:
                        sheet.write_formula(row_number, column, '=SUM(%s)' % xl_range(5, column, row_number - 1, column),
                                            total, company.currency_id.round(value))
                    else:
                        sheet.write_number(row_number, column, 0, total)
            return output.getvalue()

    def action_download(self):
        self.ensure_one()
        self.check_access('write')
        self.file_data = base64.b64encode(self._xlsx())
        filename = f'libro-{self.book}-{self.year:04d}-{self.month.zfill(2)}.xlsx'
        return {
            'type': 'ir.actions.act_url', 'target': 'download',
            'url': f'/web/content/{self._name}/{self.id}/file_data/{filename}?download=true',
        }
