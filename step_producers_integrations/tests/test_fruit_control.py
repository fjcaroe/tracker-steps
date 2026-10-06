from odoo.tests import TransactionCase, tagged
from odoo.tools.safe_eval import safe_eval


@tagged('post_install', '-at_install')
class TestProducerFruitControl(TransactionCase):
    def test_original_relations_and_mixed_producer_quantities(self):
        producers = self.env['res.partner'].create([
            {'name': 'Control productor A', 'is_productor': True},
            {'name': 'Control productor B', 'is_productor': True}])
        product = self.env['product.product'].create({'name': 'Caja control', 'type': 'consu'})
        tag = self.env['stock.quant.package'].create({
            'name': 'Tarja control mixta', 'is_fruit_tag': True, 'step_tag_kind': 'E',
            'step_tag_line_ids': [(0, 0, {'producer_id': producer.id, 'product_id': product.id,
                'quantity': boxes, 'boxes': boxes, 'kilos': boxes * 5})
                for producer, boxes in zip(producers, [2, 6])]})
        tag.action_step_validate_tag()
        ot = self.env['step.packing.production'].create({
            'product_id': product.id, 'step_packing_output_tag_ids': [(6, 0, tag.ids)]})
        shipment = self.env['step.export.export'].create({
            'name': 'Embarque control', 'tag_ids': [(6, 0, tag.ids)]})
        rows = tag.step_tag_line_ids
        self.assertEqual(rows.mapped('control_process_ids'), ot)
        self.assertEqual(rows.mapped('control_shipment_ids'), shipment)
        self.assertEqual(sorted(rows.mapped('control_pending_kg')), [10, 30])
        self.assertEqual(sum(rows.mapped('boxes')), 8)
        self.assertEqual(sum(rows.mapped('control_pallet_qty')), 1)
        self.assertEqual(rows[0].action_open_control_tag()['res_id'], tag.id)
        # No current quant is needed: dispatch must not erase historical kilos.
        self.assertFalse(tag.quant_ids)
        self.assertEqual(sum(rows.mapped('kilos')), 40)

    def test_receipts_include_drafts_and_default_the_corresponding_kind(self):
        incoming = self.env['stock.picking.type'].search([
            ('code', '=', 'incoming'), ('company_id', '=', self.env.company.id)], limit=1)
        self.env.company.step_fruit_inventory_enabled = True
        for kind, suffix in [('process', 'process'), ('packed', 'packed')]:
            action = self.env.ref('step_producer_fruit_flow.action_producer_%s_receptions' % suffix)
            picking = self.env['stock.picking'].create({
                'picking_type_id': incoming.id, 'location_id': incoming.default_location_src_id.id,
                'location_dest_id': incoming.default_location_dest_id.id, 'step_fruit_reception_kind': kind})
            self.assertEqual(picking.state, 'draft')
            self.assertIn(picking, self.env['stock.picking'].search(safe_eval(action.domain)))
            self.assertEqual(safe_eval(action.context)['default_step_fruit_reception_kind'], kind)
        self.assertNotIn(picking, self.env['stock.picking'].search(safe_eval(
            self.env.ref('step_producer_fruit_flow.action_producer_process_receptions').domain)))

    def test_material_selector_uses_existing_category_including_unused_components(self):
        category_ids = self.env['mrp.bom']._packaging_material_domain()[0][2]
        self.assertEqual(len(category_ids), 1)
        root = self.env['product.category'].browse(category_ids)
        child = self.env['product.category'].create({'name': 'Envases control QA', 'parent_id': root.id})
        material = self.env['product.product'].create({'name': 'Material sin BOM QA', 'categ_id': child.id})
        fruit = self.env['product.product'].create({'name': 'Fruta ajena a embalaje QA'})
        action = self.env.ref('step_export.action_producer_packaging_materials_category').run()
        products = self.env['product.product'].search(action['domain'])
        self.assertIn(material, products)
        self.assertNotIn(fruit, products)
        bom = self.env['mrp.bom'].create({'product_tmpl_id': fruit.product_tmpl_id.id, 'step_export_fruit': True})
        self.assertEqual(bom.step_export_packaging_category_id, root)
        self.assertFalse(material.bom_line_ids)
