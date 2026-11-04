from io import BytesIO
from zipfile import ZipFile

from lxml import etree

from odoo import Command
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestPackingProcessReport(TransactionCase):

    def test_summary_and_annex_share_signed_balance_and_pallet_totals(self):
        producer = self.env['res.partner'].create({'name': 'Productor T156'})
        product = self.env['product.product'].create({'name': 'Fruta T156'})

        def pallet(name, kind, boxes, kilos, result=False):
            return self.env['stock.quant.package'].create({
                'name': name, 'is_fruit_tag': True, 'step_tag_kind': kind,
                'step_producer_id': producer.id, 'step_packing_result': result,
                'step_tag_line_ids': [Command.create({
                    'producer_id': producer.id, 'product_id': product.id,
                    'quantity': boxes, 'boxes': boxes, 'kilos': kilos,
                })],
            })

        inputs = pallet('T156 C1', 'C', 6, 60) | pallet('T156 C2', 'C', 4, 40)
        outputs = pallet('T156 E1', 'E', 8, 80, 'export') | pallet('T156 N1', 'N', 1, 10, 'commercial')
        production = self.env['step.packing.production'].create({
            'step_packing_input_tag_ids': [Command.set(inputs.ids)],
            'step_packing_output_tag_ids': [Command.set(outputs.ids)],
            'step_packing_overweight_kg': -2.5,
        })
        payload = production._packing_report_data()
        raw, balance, packed_export, packed_national = payload['summary']
        self.assertEqual(len(raw[2]), 1)
        self.assertEqual(raw[2][0][-2:], (10, 100))
        self.assertEqual(balance[2][0], ('Kilos', 100, 80, -2.5, 10, 0, 0, 12.5))
        self.assertEqual(balance[2][1][3], -0.025)
        self.assertEqual(packed_export[3][-2:], (8, 80))
        self.assertEqual(packed_national[3][-2:], (1, 10))
        self.assertEqual([section[3][-2:] for section in payload['detail']], [(10, 100), (8, 80), (1, 10)])

        with ZipFile(BytesIO(production._packing_process_xlsx())) as book:
            main = etree.fromstring(book.read('xl/worksheets/sheet1.xml'))
            self.assertIn('-2.5', main.xpath("//*[local-name()='c' and not(@t)]/*[local-name()='v']/text()"))
            self.assertIn('-0.025', main.xpath("//*[local-name()='c' and not(@t)]/*[local-name()='v']/text()"))
