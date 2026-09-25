from odoo import Command
from odoo.tests.common import TransactionCase, tagged
from odoo.exceptions import UserError


@tagged('post_install', '-at_install')
class TestInventoryDispatch(TransactionCase):
    def picking(self, uom, weight=0, qty=2):
        product = self.env['product.product'].create({'name': 'T22 Fruit', 'uom_id': uom.id,
            'uom_po_id': uom.id, 'weight': weight, 'is_storable': True})
        warehouse = self.env['stock.warehouse'].search([('company_id', '=', self.env.company.id)], limit=1)
        return self.env['stock.picking'].create({'picking_type_id': warehouse.out_type_id.id,
            'location_id': warehouse.lot_stock_id.id,
            'location_dest_id': self.env.ref('stock.stock_location_customers').id,
            'move_ids': [Command.create({'name': product.name, 'product_id': product.id,
                'product_uom': uom.id, 'product_uom_qty': qty,
                'location_id': warehouse.lot_stock_id.id,
                'location_dest_id': self.env.ref('stock.stock_location_customers').id})]})

    def test_tonnes_convert_to_kilos(self):
        p = self.picking(self.env.ref('uom.product_uom_ton'))
        self.assertEqual(p.move_ids.fruit_tag_kilos, 2000)
        context = p.action_create_dispatch_guide()['context']
        self.assertEqual(context['default_line_ids'][0][2]['quantity_kg'], 2000)
        self.assertEqual(context['default_company_id'], p.company_id.id)

    def test_boxes_convert_by_weight_and_reference(self):
        p = self.picking(self.env.ref('uom.product_uom_unit'), weight=5, qty=120)
        p.write({'num_op': 'OP-22', 'num_ot': 'OT-22'})
        context = p.action_create_dispatch_guide()['context']
        self.assertEqual(context['default_line_ids'][0][2]['quantity_kg'], 600)
        self.assertIn('OP-22', context['default_reference'])
        self.assertIn('OT-22', context['default_reference'])

    def test_cancelled_picking_rejected(self):
        p = self.picking(self.env.ref('uom.product_uom_kgm'))
        p.action_cancel()
        with self.assertRaises(UserError):
            p.action_create_dispatch_guide()

    def test_package_in_kg_does_not_multiply_weight(self):
        p = self.picking(self.env.ref('uom.product_uom_kgm'), weight=5)
        package = self.env['stock.quant.package'].create({'name': 'T22 kg package'})
        self.env['stock.quant']._update_available_quantity(p.move_ids.product_id, p.location_id, 10, package_id=package)
        self.assertEqual(package.kilos_total, 10)

    def test_completed_partial_delivery_uses_actual_quantity(self):
        p = self.picking(self.env.ref('uom.product_uom_unit'), weight=5, qty=120)
        p.action_confirm()
        p.move_ids.quantity = 60
        p.move_ids.picked = True
        p._action_done()
        self.assertEqual(p.state, 'done')
        values = p.action_create_dispatch_guide()['context']['default_line_ids'][0][2]
        self.assertEqual(values['quantity'], 60)
        self.assertEqual(values['quantity_kg'], 300)
