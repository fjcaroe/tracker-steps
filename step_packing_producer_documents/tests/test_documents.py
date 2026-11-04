from io import BytesIO
from zipfile import ZipFile

from odoo import Command
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class PackingDocumentCase(TransactionCase):

    def test_native_order_plan_and_documents(self):
        species = self.env['step.especie'].create({'name': 'T158', 'type_especie': 'frutal',
                                                   'group_especie': 'fruta_h'})
        product = self.env['product.product'].create({'name': 'Fruta T158'})
        order = self.env['step.packing.order'].create({
            'week_start': '2026-11-02', 'week_end': '2026-11-08',
            'line_ids': [Command.create({'product_id': product.id, 'species_id': species.id,
                                         'boxes': 10, 'kilos': 15})],
        })
        self.assertEqual(order._document_data()['sections'][0][3][-2:], (10, 15))
        with ZipFile(BytesIO(order._document_xlsx())) as workbook:
            self.assertIn('xl/worksheets/sheet1.xml', workbook.namelist())
        report = self.env.ref('step_packing_producer_documents.action_order_pdf')
        html, _ = report._render_qweb_html(report.report_name, order.ids)
        self.assertIn(b'ORDEN DE PROCESO PACKING', html)

    def test_producer_period_crosses_iso_year_and_filters_other_producers(self):
        producer = self.env['res.partner'].create({'name': 'Productor T159'})
        for kind in ('reception', 'process'):
            wizard = self.env['step.packing.producer.document'].create({
                'kind': kind, 'producer_id': producer.id, 'date_from': '2025-12-28', 'date_to': '2026-01-04',
            })
            data = wizard._document_data()
            self.assertEqual(data['header'][2][1], '2025-S52, 2026-S01')
            self.assertFalse(data['sections'][0][2])
            with ZipFile(BytesIO(wizard._document_xlsx())) as workbook:
                self.assertIn('xl/worksheets/sheet1.xml', workbook.namelist())
