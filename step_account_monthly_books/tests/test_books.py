from datetime import date
from io import BytesIO
from xml.etree import ElementTree
from zipfile import ZipFile

from odoo import Command
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.tests import tagged


@tagged('post_install', '-at_install')
class TestMonthlyBooks(AccountTestInvoicingCommon):
    def tax(self, name, amount, code, kind='purchase'):
        return self.env['account.tax'].create({
            'name': name,
            'amount': amount,
            'amount_type': 'percent',
            'type_tax_use': kind,
            'l10n_cl_sii_code': code,
            'company_id': self.env.company.id,
        })

    def invoice(self, move_type, document, lines, day=date(2026, 10, 12), post=True, accounting_day=None):
        # Produce real posted tax balances with the test chart and no electronic
        # issuance. Set the Chilean document code for the reporting fixture.
        move = self.env['account.move'].create({
            'move_type': move_type,
            'invoice_date': day,
            'date': accounting_day or day,
            'partner_id': self.partner_a.id,
            'invoice_line_ids': [Command.create({
                'name': 'Item',
                'quantity': 1,
                'price_unit': value,
                'tax_ids': [Command.set(taxes.ids)],
            }) for value, taxes in lines],
        })
        if post:
            move.action_post()
            move.l10n_latam_document_type_id = self.env.ref('l10n_cl.' + document)
        return move

    def book(self, kind):
        return self.env['step.account.monthly.book'].create({'book': kind, 'month': '10', 'year': 2026})

    def test_purchases_posted_amounts_and_refund(self):
        vat = self.tax('VAT', 19, 14)
        withheld = self.tax('VAT withheld on berries', -14, 48)
        specific = self.tax('Specific tax', 11, 28)
        empty = self.env['account.tax']
        invoice = self.invoice('in_invoice', 'dc_a_f_dte', [(100000, vat | withheld | specific), (10000, empty)])
        refund = self.invoice('in_refund', 'dc_nc_f_dte', [(10000, vat)], day=date(2026, 10, 13))
        self.invoice('in_invoice', 'dc_a_f_dte', [(3000, vat)], post=False)
        self.invoice('in_invoice', 'dc_a_f_dte', [(4000, vat)], day=date(2026, 11, 1))
        wizard = self.book('purchases')
        self.assertEqual(wizard._moves().ids, [invoice.id, refund.id])
        self.assertEqual(wizard._row(1, invoice)[8:16],
                         (10000, 100000, 11000, 19000, 140000, 14000, 5000, 126000))
        self.assertEqual(wizard._row(2, refund)[8:16],
                         (0, -10000, 0, -1900, -11900, 0, None, -11900))
        with ZipFile(BytesIO(wizard._xlsx())) as xlsx:
            sheet = ElementTree.fromstring(xlsx.read('xl/worksheets/sheet1.xml'))
        ns = {'m': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
        total = sheet.find(".//m:c[@r='P8']", ns)
        self.assertEqual(total.find('m:f', ns).text, 'SUM(P6:P7)')
        self.assertEqual(float(total.find('m:v', ns).text), 114100)

    def test_sales_and_fee_books(self):
        vat = self.tax('Sales VAT', 19, 14, 'sale')
        retention = self.tax('Fees withholding', -15.25, 15)
        empty = self.env['account.tax']
        sale = self.invoice('out_invoice', 'dc_a_f_dte', [(100000, vat)])
        taxed = self.invoice('in_invoice', 'dc_m_d_dtn', [(100000, retention)])
        exempt = self.invoice('in_invoice', 'dc_m_d_dtn', [(10000, empty)], day=date(2026, 10, 13))
        sales = self.book('sales')
        self.assertEqual(sales._moves(), sale)
        self.assertEqual(sales._row(1, sale)[7:13], (100000, 19000, 119000, 0, None, 119000))
        fees = self.book('fees')
        self.assertEqual(fees._moves(), taxed + exempt)
        self.assertEqual(fees._row(1, taxed)[7:11], (0, 100000, 15250, 84750))
        self.assertEqual(fees._row(2, exempt)[7:11], (10000, 10000, 0, 10000))
        self.assertFalse(self.book('purchases')._moves())
        self.assertEqual(fees.action_download()['target'], 'download')

    def test_period_uses_posting_date_for_purchases_and_fees(self):
        september = date(2026, 9, 30)
        october = date(2026, 10, 1)
        november = date(2026, 11, 1)
        empty = self.env['account.tax']

        for book, document in (('purchases', 'dc_y_f_dte'), ('fees', 'dc_m_d_dtn')):
            with self.subTest(book=book):
                brought_forward = self.invoice('in_invoice', document, [(10000, empty)],
                                               day=september, accounting_day=october)
                deferred = self.invoice('in_invoice', document, [(20000, empty)],
                                        day=october, accounting_day=november)
                self.assertEqual((brought_forward.invoice_date, brought_forward.date), (september, october))
                self.assertEqual((deferred.invoice_date, deferred.date), (october, november))
                october_book = self.book(book)
                self.assertEqual(october_book._moves(), brought_forward)
                self.assertEqual(october_book._row(1, brought_forward)[7 if book == 'purchases' else 5], september)
                october_book.month = '11'
                self.assertEqual(october_book._moves(), deferred)

        sales = self.book('sales')
        sale = self.invoice('out_invoice', 'dc_a_f_dte', [(10000, empty)],
                            day=october, accounting_day=november)
        self.assertEqual((sale.invoice_date, sale.date), (october, november))
        self.assertEqual(sales._moves(), sale)
