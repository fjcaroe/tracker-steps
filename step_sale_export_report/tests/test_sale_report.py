from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class SaleExportReportCase(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env['res.partner'].create({'name': 'Report test receiver', 'lang': 'en_US'})
        product_vals = {'name': 'Report test fruit', 'type': 'service', 'step_export_enabled': True}
        if 'grupo_labor' in cls.env['product.product']._fields:
            product_vals['grupo_labor'] = 'pack'
        cls.product = cls.env['product.product'].create(product_vals)

    def order(self):
        return self.env['sale.order'].create({'partner_id': self.partner.id, 'step_export_sale': True,
            'order_line': [(0, 0, {'product_id': self.product.id, 'product_uom_qty': 10,
                'price_unit': 20, 'discount': 10, 'tax_id': [(5, 0, 0)], 'step_export_kg': 100, 'step_export_boxes': 10}),
                (0, 0, {'product_id': self.product.id, 'product_uom_qty': 1, 'price_unit': 30,
                    'tax_id': [(5, 0, 0)], 'step_export_charge': 'freight'}),
                (0, 0, {'product_id': self.product.id, 'product_uom_qty': 1, 'price_unit': 5,
                    'tax_id': [(5, 0, 0)], 'step_export_charge': 'insurance'})]})

    def test_financial_breakdown_preserves_native_totals(self):
        order = self.order()
        values = order._step_export_report_values()
        self.assertEqual(values['subtotal'], 180)
        self.assertEqual(values['freight'], 30)
        self.assertEqual(values['insurance'], 5)
        self.assertEqual(order.amount_total, 215)
        self.assertEqual(len(values['lines']), 1)
        tax = self.env['account.tax'].create({'name': 'Report test 19%', 'amount': 19, 'amount_type': 'percent', 'type_tax_use': 'sale'})
        order.order_line.tax_id = tax
        values = order._step_export_report_values()
        self.assertAlmostEqual(values['subtotal'] + values['freight'] + values['insurance'] + order.amount_tax, order.amount_total)

    def test_negative_quantities_rejected(self):
        line = self.order().order_line[0]
        with self.assertRaises(ValidationError), self.cr.savepoint():
            line.step_export_kg = -1
        with self.assertRaises(ValidationError), self.cr.savepoint():
            line.step_export_boxes = -1

    def test_bank_company_ownership(self):
        partner = self.env['res.partner'].create({'name': 'Unrelated account owner'})
        bank = self.env['res.partner.bank'].create({'acc_number': 'TEST-ONLY-62', 'partner_id': partner.id})
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self.env.company.step_export_bank_id = bank

    def test_standard_report_switch_is_company_scoped(self):
        order = self.order()
        report = self.env['ir.actions.report']
        order.company_id.step_export_sale_format = False
        html, _ = report._render_qweb_html('sale.report_saleorder_pro_forma', order.ids)
        self.assertNotIn(b'step_export_document', html)
        order.company_id.step_export_sale_format = True
        html, _ = report._render_qweb_html('sale.report_saleorder_pro_forma', order.ids)
        self.assertIn(b'step_export_document', html)
        self.assertIn(order._step_export_report_title(True).encode(), html)
        self.assertIn(b'Report test fruit', html)

    def test_dedicated_print_actions_and_missing_bank(self):
        order = self.order()
        order.company_id.step_export_bank_id = False
        for xmlid, proforma in [('action_sale_note', False), ('action_proforma', True)]:
            report = self.env.ref('step_sale_export_report.' + xmlid)
            self.assertEqual(report.binding_model_id.model, 'sale.order')
            html, _ = report._render_qweb_html(report.report_name, order.ids)
            self.assertIn(order._step_export_report_title(proforma).encode(), html)
            self.assertIn(b'Wire Instructions:', html)
            self.assertIn(b'pendientes', html)
