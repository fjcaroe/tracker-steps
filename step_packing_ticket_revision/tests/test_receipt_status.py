from odoo.tests import TransactionCase, tagged
from odoo.tools.safe_eval import safe_eval


@tagged('post_install', '-at_install')
class ReceiptStatusCase(TransactionCase):
    def test_only_completed_returns_exclude_original_and_keep_history(self):
        wh = self.env['stock.warehouse'].search([('company_id', '=', self.env.company.id)], limit=1)
        source = self.env['stock.picking'].create({'picking_type_id': wh.in_type_id.id,
            'location_id': wh.in_type_id.default_location_src_id.id, 'location_dest_id': wh.lot_stock_id.id})
        returned = self.env['stock.picking'].create({'picking_type_id': wh.out_type_id.id,
            'location_id': wh.lot_stock_id.id, 'location_dest_id': wh.out_type_id.default_location_dest_id.id,
            'return_id': source.id})
        self.assertFalse(source.step_has_fruit_return)
        returned.write({'state': 'done'})
        self.assertTrue(source.step_has_fruit_return)
        current = self.env['stock.picking'].search([('id', '=', source.id), ('step_has_fruit_return', '=', False)])
        self.assertFalse(current)
        self.assertEqual(self.env['stock.picking'].search([('id', '=', source.id), ('step_has_fruit_return', '=', True)]), source)
        self.assertTrue(source.exists())
        returned.write({'state': 'cancel'})
        self.assertFalse(source.step_has_fruit_return)
        self.assertEqual(self.env['stock.picking'].search([('id', '=', source.id), ('step_has_fruit_return', '=', False)]), source)
        for suffix in ('process', 'packed'):
            report = self.env.ref('step_producer_fruit_reports.action_' + suffix)
            self.assertIn(('picking_id.step_has_fruit_return', '=', False), safe_eval(report.domain))
            action = self.env.ref('step_inventory_packing.action_steps_fruit_' + suffix + '_reception')
            self.assertEqual(safe_eval(action.context)['search_default_fruit_current'], 1)
            self.assertIn(('step_has_fruit_return', '=', False), safe_eval(action.domain))
