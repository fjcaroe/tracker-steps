from lxml import etree
from odoo.tests import TransactionCase, tagged
from odoo.tools.safe_eval import safe_eval

from ..models.sale_order import APR_FIELDS


@tagged('post_install', '-at_install')
class TestExportSale(TransactionCase):

    def test_selector_preserves_standard_domain_and_filters_export_products(self):
        tree = etree.fromstring(self.env['sale.order'].get_view(view_type='form')['arch'].encode())
        nodes = tree.xpath(".//field[@name='order_line']//field[@name='product_id' or @name='product_template_id'][@domain]")
        self.assertTrue(nodes)
        for node in nodes:
            for export in (True, False):
                domain = safe_eval(node.get('domain'), {'parent': type('Order', (), {
                    'step_export_sale_context': export, 'company_id': self.env.company.id})()})
                self.assertIn(('sale_ok', '=', True), domain)
                self.assertEqual(('step_export_enabled', '=', True) in domain, export)

    def test_apr_visibility_tracks_actual_company_configuration(self):
        company = self.env.company
        available = [name for name in ('product_fijo', 'product_consu') if name in company._fields]
        if not available:
            self.assertFalse(self.env['sale.order'].new({'company_id': company.id}).step_apr_configured)
            return
        company.write({name: False for name in available})
        order = self.env['sale.order'].new({'company_id': company.id})
        self.assertFalse(order.step_apr_configured)
        product = self.env['product.product'].create({'name': 'APR configuration QA', 'grupo_labor': 'pack'})
        for name in available:
            company.write({name: product.id})
            self.assertTrue(order.step_apr_configured)
            company.write({name: False})
            self.assertFalse(order.step_apr_configured)
        tree = etree.fromstring(self.env['sale.order'].get_view(view_type='form')['arch'].encode())
        for node in tree.xpath('.//field'):
            if node.get('name') in APR_FIELDS:
                self.assertIn('not step_apr_configured', node.get('invisible', ''))

    def test_catalog_and_existing_export_links_use_same_filter(self):
        product = self.env['product.product'].create({'name': 'Export sale QA', 'grupo_labor': 'pack', 'step_export_enabled': True})
        regular = self.env['product.product'].create({'name': 'Ordinary sale QA', 'grupo_labor': 'pack', 'step_export_enabled': False})
        export = self.env['sale.order'].new({'step_export_sale': True})
        products = self.env['product.product'].search(export._get_product_catalog_domain())
        self.assertIn(product, products)
        self.assertNotIn(regular, products)
        ordinary = self.env['sale.order'].new({})
        self.assertIn(regular, self.env['product.product'].search(ordinary._get_product_catalog_domain()))
        shipment = self.env['step.export.export'].create({'name': 'Historical export link QA'})
        historical = self.env['sale.order'].new({'step_export_shipment_id': shipment.id})
        self.assertFalse(historical.step_export_sale)
        self.assertTrue(historical.step_export_sale_context)
        self.assertIn(('step_export_enabled', '=', True), historical._get_product_catalog_domain())
