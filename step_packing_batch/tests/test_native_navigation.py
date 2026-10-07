from odoo.tests.common import TransactionCase, new_test_user, tagged


@tagged('post_install', '-at_install')
class TestNativePackingNavigation(TransactionCase):
    def test_transfers_remain_available_to_inventory_operator(self):
        menu = self.env.ref('step_packing_batch.menu_packing_fruta_batch')
        self.assertEqual(menu.parent_id, self.env.ref('step_packing_operations.menu_packing_operations_dispatch'))
        self.assertEqual(menu.action, self.env.ref('stock_picking_batch.stock_picking_batch_action'))
        operator = new_test_user(self.env, login='packing_batch_operator_qa', groups='stock.group_stock_user')
        self.assertIn(menu.id, self.env['ir.ui.menu'].with_user(operator)._visible_menu_ids())
        self.env['stock.picking.batch'].with_user(operator).get_view(view_type='form')

    def test_history_keeps_original_menu_ids_and_is_idempotent(self):
        history = self.env.ref('step_environment_policy.packing_history')
        originals = [self.env.ref(xmlid) for xmlid in (
            'step_packing.menu_step_packing_root', 'step_packing.menu_packing_fruta_root')]
        identities = [menu.id for menu in originals]
        for menu in originals:
            self.assertEqual(menu.parent_id, history)
        self.assertEqual(history.groups_id, self.env.ref('base.group_system'))
        self.env['ir.ui.menu']._step_normalize_agriculture_menus()
        self.assertEqual(self.env.ref('step_environment_policy.packing_history'), history)
        self.assertEqual([menu.id for menu in originals], identities)
        for menu in originals:
            self.assertEqual(menu.parent_id, history)
