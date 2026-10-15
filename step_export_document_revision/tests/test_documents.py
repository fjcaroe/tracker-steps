import io
import zipfile
from lxml import etree
from odoo import Command
from odoo.exceptions import ValidationError, UserError, AccessError
from odoo.tests.common import TransactionCase, tagged, new_test_user


@tagged('post_install', '-at_install')
class DocumentCase(TransactionCase):
    def sample(self):
        company = self.env['res.company'].create({'name': 'QA Document Exporter',
            'currency_id': self.env.ref('base.USD').id, 'country_id': self.env.ref('base.cl').id, 'step_export_sale_format': True})
        env = self.env(context=dict(self.env.context, allowed_company_ids=company.ids, chart_template_load=True,
                                    tracking_disable=True, mail_create_nosubscribe=True))
        env['ir.sequence'].create({'name': 'QA Packing Lists', 'code': 'step.export.packing.list',
            'prefix': 'QA-PL/', 'padding': 4, 'company_id': company.id})
        partner = env['res.partner'].create({'name': 'QA Document Importer', 'lang': 'es_CL', 'cod_csg': 'QA-CSG'})
        product = env['product.product'].create({'name': 'QA Export Fruit', 'type': 'consu',
            'step_export_enabled': True, 'weight': 5, 'is_fruta': True})
        packaging = env['product.packaging'].create({'name': 'QA 5 kg box', 'product_id': product.id,
            'qty': 1, 'step_export_kg_per_box': 5})
        order = env['sale.order'].create({'partner_id': partner.id, 'company_id': company.id,
            'step_export_sale': True, 'order_line': [Command.create({'product_id': product.id,
                'product_uom_qty': 10, 'product_packaging_id': packaging.id, 'price_unit': 3, 'tax_id': [Command.clear()]})]})
        shipment = env['step.export.export'].create({'name': 'QA Document Shipment', 'shipment_number': 'QA-DOC-85', 'receiver_id': partner.id,
            'company_id': company.id, 'booking': 'QA BOOKING', 'departure_date': '2026-11-01', 'arrival_date': '2026-12-01',
            'line_ids': [Command.create({'product_id': product.id, 'pallet_qty': 1, 'boxes_per_pallet': 10, 'kg_per_box': 5})]})
        order.step_export_shipment_id = shipment
        guide = env['step.dispatch.guide'].create({'external_folio': 'QA-DOC-85', 'partner_id': partner.id,
            'company_id': company.id, 'origin_address': 'QA Origin', 'destination_address': 'QA Destination',
            'carrier_id': partner.id, 'truck_plate': 'QA0085', 'step_export_shipment_id': shipment.id})
        plant = env['res.partner'].create({'name': 'QA Packing Plant', 'step_packing_csp': 'QA-CSP'})
        ot = env['step.packing.production'].create({'company_id': company.id, 'date': '2026-10-15', 'packing_partner_id': plant.id})
        tag = env['stock.quant.package'].create({'name': 'QA-PALLET-85', 'is_fruit_tag': True, 'step_tag_kind': 'E',
            'step_producer_id': partner.id, 'owner_id': partner.id, 'box_count': 10,
            'step_packing_production_id': ot.id, 'step_export_gross_kg': 53, 'step_export_thermos': 'QA-T85',
            'step_tag_line_ids': [Command.create({'product_id': product.id, 'producer_id': partner.id,
                'quantity': 10, 'kilos': 50})]})
        shipment.tag_ids = tag
        packing = env['step.export.packing.list'].create({'shipment_id': shipment.id, 'guide_id': guide.id, 'tag_ids': [Command.set(tag.ids)]})
        return order, packing

    def test_box_and_kg_tax_discount_and_standard_invoice(self):
        order, _ = self.sample(); line = order.order_line
        self.assertFalse(order.step_price_kg); self.assertEqual(line.step_document_kg, 50)
        self.assertEqual(order.amount_total, 30)
        order.step_price_kg = True; self.assertEqual(order.amount_total, 150)
        group = order.env['account.tax.group'].create({'name': 'QA VAT', 'company_id': order.company_id.id})
        tax = order.env['account.tax'].create({'name': 'QA VAT', 'amount': 19, 'type_tax_use': 'sale',
            'tax_group_id': group.id, 'country_id': self.env.ref('base.cl').id})
        line.write({'tax_id': [Command.set(tax.ids)], 'discount': 10})
        self.assertAlmostEqual(line.price_subtotal, 135); self.assertAlmostEqual(order.amount_total, 160.65)
        vals = line._prepare_invoice_line(); self.assertEqual(vals['price_unit'], 15)
        self.assertEqual(vals['discount'], 10)
        line.product_packaging_id.step_export_kg_per_box = 8
        self.assertEqual(line.step_document_kg, 50); self.assertEqual(line._prepare_invoice_line()['price_unit'], 15)
        self.assertEqual(line.product_uom_qty, 10)
        line.product_id.invoice_policy = 'order'
        order.state = 'sale'
        self.assertAlmostEqual(line.untaxed_amount_to_invoice, 135)

    def test_legacy_opt_in_and_confirmed_mode_lock(self):
        order, _ = self.sample()
        order.step_box_pricing = False
        line = order.order_line; line.write({'product_uom_qty': 50, 'step_export_boxes': 10, 'price_unit': 3})
        self.assertEqual(order.amount_total, 150)
        order.action_apply_box_pricing(); self.assertEqual(line.product_uom_qty, 10); self.assertEqual(order.amount_total, 30)
        order.state = 'sale'
        with self.assertRaises(UserError), self.cr.savepoint(): order.step_price_kg = True

    def test_missing_packaging_and_wrong_product_rejected(self):
        order, _ = self.sample()
        order.step_price_kg = True
        with self.assertRaises(ValidationError), self.cr.savepoint(): order.order_line.product_packaging_id = False

    def test_english_documents_and_no_accounting_side_effects(self):
        order, _ = self.sample(); reports = order.env['ir.actions.report']
        count = order.env['account.move'].search_count([])
        for name, title in [('step_sale_export_report.proforma', b'PROFORMA'),
                            ('step_export_document_revision.commercial_invoice', b'INVOICE')]:
            html, _ = reports._render_qweb_html(name, order.ids)
            self.assertIn(title, html); self.assertIn(b'Product details', html); self.assertIn(b'Customer:', html)
            self.assertNotIn(b'Detalle de producto', html)
        self.assertEqual(order.env['account.move'].search_count([]), count)
        self.assertEqual(order.action_print_export_invoice()['report_name'], 'step_export_document_revision.commercial_invoice')

    def test_packing_pdf_excel_parity_and_no_formulas(self):
        _, packing = self.sample(); rows = packing._document_rows()
        self.assertEqual(rows[0][0], 'QA-CSP'); self.assertEqual(rows[0][3], '2026-10-15')
        self.assertEqual(rows[0][4], 'QA-CSG'); self.assertEqual(rows[0][5:8], [10, 50, 53])
        self.assertEqual(packing.kg_qty, 50)
        packing.shipment_id.write({'origin_port': 'QA departure', 'destination_port': 'QA arrival'})
        header = dict(packing._document_header())
        self.assertEqual(header['POD'], 'QA departure'); self.assertEqual(header['POL'], 'QA arrival')
        self.assertEqual(header['TOTAL BOXES'], 10); self.assertEqual(header['NET WEIGHT'], 50)
        self.assertEqual(header['INVOICE'], packing.shipment_id.sale_order_ids.export_document_number)
        packing.tag_ids.step_export_thermos = '=1+1'
        book = zipfile.ZipFile(io.BytesIO(packing._document_xlsx()))
        xml = book.read('xl/worksheets/sheet1.xml')
        self.assertNotIn(b'<f>', xml); self.assertIn(b'QA-CSG', book.read('xl/sharedStrings.xml'))
        html, _ = packing.env['ir.actions.report']._render_qweb_html('step_export.action_report_export_packing_list', packing.ids)
        self.assertIn(b'QA-CSP', html); self.assertIn(b'GROSS WEIGHT', html)

    def test_forms_and_cross_company_permissions(self):
        order, packing = self.sample()
        user = new_test_user(order.env, login='qa-doc-operator', groups='sales_team.group_sale_salesman,stock.group_stock_user',
            company_id=order.company_id.id, company_ids=[Command.set(order.company_id.ids)])
        order.user_id = user
        tree = etree.fromstring(order.with_user(user).get_view(view_type='form')['arch'].encode())
        self.assertTrue(tree.xpath('.//button[@name="action_print_export_invoice"]'))
        self.assertTrue(tree.xpath('.//field[@name="step_price_kg"]'))
        fields = tree.xpath('.//field[@name="order_line"]/list/field/@name')
        self.assertLess(fields.index('product_packaging_id'), fields.index('step_document_uom_id'))
        self.assertLess(fields.index('step_document_uom_id'), fields.index('step_document_kg'))
        packing.with_user(user)._document_xlsx()
        other = new_test_user(self.env, login='qa-doc-other', groups='sales_team.group_sale_salesman,stock.group_stock_user',
            company_id=self.env.company.id, company_ids=[Command.set(self.env.company.ids)])
        with self.assertRaises(AccessError): packing.with_user(other).action_export_excel()
