# -*- coding: utf-8 -*-
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install', 'step_export')
class TestPackingFrutaMenus(TransactionCase):

    def test_export_pieces_in_packing_fruta(self):
        expected = {
            'step_export.menu_packing_fruta_estimate': 'step_packing.menu_packing_fruta_planning',
            'step_export.menu_packing_fruta_stock_reservation': 'step_packing.menu_packing_fruta_receptions',
            'step_export.menu_packing_fruta_dispatch_order': 'step_packing.menu_packing_fruta_dispatch_root',
            'step_export.menu_packing_fruta_vessel': 'step_packing.menu_packing_fruta_config_export',
        }
        for menu_xmlid, parent_xmlid in expected.items():
            menu = self.env.ref(menu_xmlid)
            self.assertEqual(menu.parent_id, self.env.ref(parent_xmlid), menu_xmlid)
            self.assertTrue(menu.action, menu_xmlid)
