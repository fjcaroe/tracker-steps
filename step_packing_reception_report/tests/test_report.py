from lxml import html
from odoo import fields
from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged, new_test_user
from .common import receipt_fixture


@tagged('post_install','-at_install')
class ReceiptReportCase(TransactionCase):
    def setUp(self):
        super().setUp()
        self.picking = receipt_fixture(self.env)

    def render(self, picking=None):
        return self.env['ir.actions.report']._render_qweb_html('stock.action_report_delivery',(picking or self.picking).ids)[0].decode()

    def test_reference_values_and_physical_counts(self):
        totals=self.picking._step_receipt_totals()
        self.assertEqual(totals['pallets'],3)
        self.assertEqual(totals['containers'],600)
        self.assertEqual(totals['boxes'],600)
        self.assertAlmostEqual(totals['gross'],1452.50)
        self.assertAlmostEqual(totals['tare'],252)
        self.assertAlmostEqual(totals['net'],1200.50)
        self.assertAlmostEqual(totals['average'],1200.50/600)
        self.assertEqual(totals['units'][0]['received'],1200.50)

    def test_receipt_header_and_details_in_native_action(self):
        tree=html.fromstring(self.render())
        self.assertIn('RECIBO DE RECEPCIÓN',tree.text_content())
        self.assertIn('QA-GUIA-141',tree.text_content())
        self.assertIn('QA recibo clase',tree.text_content())
        self.assertEqual(len(tree.xpath("//table[contains(@class,'step_receipt_pallets')]/tbody/tr")),3)
        self.assertTrue(tree.xpath("//table[contains(@class,'step_receipt_transport')]"))
        self.assertFalse(tree.xpath("//table[@name='stock_move_table' or @name='stock_move_line_table']"))

    def test_completed_receipt_keeps_custom_format(self):
        # No stock is invented for the report: only set state inside the isolated
        # test transaction to exercise native done-template routing.
        self.picking.write({'state':'done','date_done':fields.Datetime.now()})
        self.assertIn('step_receipt_pallets',self.render())
        self.assertEqual(self.picking._step_receipt_totals()['units'][0]['received'],1200.50)

    def test_other_stock_documents_remain_native(self):
        self.picking.step_fruit_reception_kind=False
        tree=html.fromstring(self.render())
        self.assertFalse(tree.xpath("//table[contains(@class,'step_receipt_')]"))
        self.assertTrue(tree.xpath("//table[@name='stock_move_table']"))
        self.picking.step_fruit_reception_kind='process'
        warehouse=self.picking.picking_type_id.warehouse_id
        self.picking.picking_type_id=warehouse.out_type_id
        self.assertFalse(self.picking._step_is_fruit_receipt())

    def test_weighted_average_and_zero_boxes(self):
        lines=self.picking.fruit_tag_line_ids
        lines[0].quantity=100;lines[1].quantity=300;lines[2].quantity=0
        self.assertAlmostEqual(self.picking._step_receipt_totals()['average'],1200.50/400)
        lines.quantity=0
        self.assertEqual(self.picking._step_receipt_totals()['average'],0)
        self.assertIn('step_receipt_pallets',self.render())

    def test_mixed_units_not_added_together(self):
        unit=self.env.ref('uom.product_uom_unit')
        product=self.env['product.product'].create({'name':'QA recibo unidad','is_storable':True})
        self.env['stock.move'].create({'name':'QA unidad','picking_id':self.picking.id,'product_id':product.id,
            'product_uom':unit.id,'product_uom_qty':7,'location_id':self.picking.location_id.id,
            'location_dest_id':self.picking.location_dest_id.id})
        groups=self.picking._step_receipt_totals()['units']
        self.assertEqual(len(groups),2)
        self.assertEqual(sorted(g['ordered'] for g in groups),[7,1200.50])

    def test_helpers_reject_other_company(self):
        other=self.env['res.company'].create({'name':'QA recibo ajeno'})
        user=new_test_user(self.env(context=dict(self.env.context,no_reset_password=True)),login='qa-141-denied',
            groups='stock.group_stock_manager',company_id=other.id,company_ids=[(6,0,other.ids)])
        record=self.picking.with_user(user).with_context(allowed_company_ids=other.ids)
        with self.assertRaises(AccessError):record._step_receipt_totals()
        with self.assertRaises(AccessError):record._step_is_fruit_receipt()

    def test_render_does_not_change_saved_weights(self):
        lines=self.picking.fruit_tag_line_ids
        fields_to_check=['quantity','gross_kg','tare_kg','kilos','write_date']
        before=lines.read(fields_to_check)
        self.render()
        self.assertEqual(lines.read(fields_to_check),before)
        self.assertFalse(self.env.ref('stock.action_report_delivery').attachment_use)
