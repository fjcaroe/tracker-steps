from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestHarvestInventory(TransactionCase):
    def test_receipt_keeps_work_order_and_waits_for_warehouse(self):
        product = self.env['product.template'].create({'name': 'T22 Harvest fruit',
            'uom_id': self.env.ref('uom.product_uom_kgm').id,
            'uom_po_id': self.env.ref('uom.product_uom_kgm').id})
        harvest = self.env['step.cosecha.registry'].create({'name': 'T22-HARVEST',
            'mobile_work_order': 'OT-T22', 'type_tarea': 'contratista',
            'partner_id': self.env['res.partner'].create({'name': 'T22 Contractor'}).id,
            'product_id': product.id, 'product_uom_id': product.uom_id.id})
        # The existing reception document supplies quantities without forcing
        # payroll/costing data, which is outside this inventory bridge.
        reception = self.env['step.cosecha.recepcion'].create({'name': 'T22 Reception', 'registry_id': harvest.id,
            'recep_line': [(0, 0, {'product_id': product.id, 'uom_id': product.uom_id.id, 'quantity': 12})]})
        harvest.recibir_cosecha(reception_id=reception.id)
        self.assertEqual(harvest.reception_picking_id.num_ot, 'OT-T22')
        self.assertNotEqual(harvest.reception_picking_id.state, 'done')
        self.assertEqual(harvest.reception_picking_id.move_ids.product_uom_qty, 12)
