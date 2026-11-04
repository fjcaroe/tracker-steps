from io import BytesIO
from unittest.mock import patch
from zipfile import ZipFile

from odoo import Command
from odoo.addons.step_packing_operations.models.process_control import _INTERNAL
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


    def test_process_rows_and_explicit_mail_queue(self):
        producer = self.env['res.partner'].create({'name': 'QA Productor', 'email': 'packing@example.invalid'})
        product = self.env['product.product'].create({'name': 'QA Fruta'})
        input_tag = self.env['stock.quant.package'].create({
            'name': 'QA-T160-C', 'is_fruit_tag': True, 'step_tag_kind': 'C',
            'step_producer_id': producer.id, 'step_tag_line_ids': [Command.create({
                'producer_id': producer.id, 'product_id': product.id, 'quantity': 10,
                'boxes': 10, 'kilos': 100,
            })],
        })
        production = self.env['step.packing.production'].create({
            'date': '2026-11-02', 'fruit_grower_id': producer.id,
            'step_packing_input_tag_ids': [Command.set(input_tag.ids)],
            'step_packing_overweight_kg': -2,
        })
        production.with_context(_packing_control=_INTERNAL).state = 'validated'
        wizard = self.env['step.packing.producer.document'].create({
            'kind': 'process', 'producer_id': producer.id,
            'date_from': '2026-11-02', 'date_to': '2026-11-08',
        })
        section = wizard._document_data()['sections'][0]
        self.assertEqual(section[2][0][2], production.name)
        self.assertEqual(section[3][5], 100)
        self.assertEqual(section[3][9], -2)
        reports = type(self.env['ir.actions.report'])
        with patch.object(reports, '_render_qweb_pdf', return_value=(b'%PDF-fixture', 'pdf')):
            wizard.action_document_email()
        mail = self.env['mail.mail'].search([('email_to', '=', 'packing@example.invalid')])
        self.assertEqual(mail.state, 'outgoing')
        self.assertEqual(len(mail.attachment_ids), 2)
