from odoo.exceptions import ValidationError
from odoo.tests import Form, TransactionCase, tagged


@tagged('post_install', '-at_install')
class PackagingMasterCase(TransactionCase):
    def packaging(self):
        product = self.env['product.product'].create({'name': 'QA Embalaje T124'})
        return self.env['product.packaging'].create({'name': 'QA T124', 'product_id': product.id,
            'qty': 3.8, 'step_export_kg_per_box': 3.8, 'step_clamshell_qty': 12,
            'step_clamshell_weight_g': 340, 'step_boxes_per_pallet': 204,
            'step_pallets_per_container': 20})

    def test_requested_formula_and_recomputation(self):
        row = self.packaging()
        self.assertEqual(row.step_boxes_per_container_40, 4080)
        self.assertAlmostEqual(row.step_net_pallet_weight, 775.2)
        row.step_export_kg_per_box = 4
        self.assertEqual(row.step_net_pallet_weight, 816)
        row.step_boxes_per_pallet = 100
        self.assertEqual(row.step_boxes_per_container_40, 2000)
        self.assertEqual(row.step_net_pallet_weight, 400)
        self.assertEqual(row.qty, 3.8)
        Form(row, view='step_export.view_step_export_packaging_form')

    def test_negative_capacity_rejected(self):
        row = self.packaging()
        for name in ('step_clamshell_qty', 'step_clamshell_weight_g', 'step_boxes_per_pallet', 'step_pallets_per_container'):
            with self.assertRaises(ValidationError), self.cr.savepoint():
                row[name] = -1

    def test_existing_category_lowercase_and_children_selectable(self):
        model = self.env['mrp.bom']
        roots = self.env['product.category'].browse(model._packaging_material_domain()[0][2])
        self.assertEqual(len(roots), 1)
        roots.name = '6 materiales de embalajes'
        child = self.env['product.category'].create({'name': 'QA materiales caja', 'parent_id': roots.id})
        material = self.env['product.product'].create({'name': 'QA material T125', 'categ_id': child.id})
        self.assertIn(material, self.env['product.product'].search(model._packaging_material_domain()))
        bom = model.create({'product_tmpl_id': self.packaging().product_id.product_tmpl_id.id,
                            'step_export_fruit': True,
                            'bom_line_ids': [(0, 0, {'product_id': material.id, 'product_qty': 12})]})
        self.assertEqual(bom.bom_line_ids.product_id, material)
        self.assertEqual(bom.step_export_packaging_category_id, roots)
        Form(bom, view='step_export.view_export_fruit_bom_form')

    def test_ambiguous_master_is_rejected(self):
        self.env['product.category'].create({'name': 'MATERIALES DE EMBALAJE'})
        with self.assertRaises(ValidationError):
            self.env['mrp.bom']._packaging_material_domain()

    def test_packing_menu_reuses_original_action_and_model(self):
        menu = self.env.ref('step_packing_packaging_master.menu_packing_fruit_bom')
        self.assertEqual(menu.action, self.env.ref('step_export.action_export_fruit_bom'))
        self.assertEqual(menu.action.res_model, 'mrp.bom')
