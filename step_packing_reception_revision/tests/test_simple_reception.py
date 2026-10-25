from lxml import etree
from odoo.tests import TransactionCase, tagged
from odoo.exceptions import ValidationError


@tagged('post_install', '-at_install')
class SimpleReceptionCase(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.company.step_fruit_inventory_enabled = True
        cls.wh = cls.env['stock.warehouse'].search([('company_id', '=', cls.env.company.id)], limit=1)
        cls.producer = cls.env['res.partner'].create({'name': 'QA T120 productor', 'is_productor': True})
        cls.fundo = cls.env['step.fundo'].create({'name': 'QA T120 fundo', 'partner_id': cls.producer.id,
                                               'company_id': cls.env.company.id})
        cls.species = cls.env['step.especie'].create({'name': 'QA T120 especie'})
        kg = cls.env.ref('uom.product_uom_kgm')
        cls.product = cls.env['product.product'].create({'name': 'QA T120 fruta kg', 'is_storable': True,
                                                        'uom_id': kg.id, 'uom_po_id': kg.id})
        cls.packaging = cls.env['product.packaging'].create({'name': 'QA T120 caja 8kg',
                                                          'product_id': cls.product.id, 'qty': 8})

    def receipt(self, splits=(400,), demand=400, product=None, packaging=None):
        product = product or self.product
        packaging = packaging or self.packaging
        picking = self.env['stock.picking'].create({
            'partner_id': self.producer.id, 'picking_type_id': self.wh.in_type_id.id,
            'location_id': self.wh.in_type_id.default_location_src_id.id,
            'location_dest_id': self.wh.lot_stock_id.id, 'step_fruit_reception_kind': 'process',
            'fruit_fundo_id': self.fundo.id, 'fruit_species_id': self.species.id,
            'step_fruit_type': 'conventional', 'step_fruit_gross_kg': sum(splits)})
        move = self.env['stock.move'].create({
            'name': 'QA T120 fruta', 'picking_id': picking.id, 'product_id': product.id,
            'product_uom': product.uom_id.id, 'product_uom_qty': demand,
            'location_id': picking.location_id.id, 'location_dest_id': picking.location_dest_id.id,
            'product_packaging_id': packaging.id})
        move._action_confirm(merge=False)
        move.quantity = sum(splits) if product.uom_id == self.product.uom_id else sum(splits)/8
        for index, kilos in enumerate(splits):
            self.env['step.packing.picking.tag.line'].create({
                'picking_id': picking.id, 'tag_number': 'QA120-%s-%s' % (picking.id, index),
                'packaging_id': packaging.id, 'quantity': kilos/8, 'kilos': kilos})
        return picking

    def assert_received(self, picking):
        self.assertEqual(picking.state, 'done')
        for row in picking.fruit_tag_line_ids:
            package = row.package_id
            self.assertEqual(package.step_tag_kind, 'C')
            self.assertEqual(package.step_tag_state, 'validated')
            self.assertEqual(package.step_process_reception_id, picking)
            self.assertEqual(package.fundo_id, self.fundo)
            self.assertEqual(package.especie_id, self.species)
            self.assertEqual(package.fruit_type, 'conventional')
            self.assertEqual(package.box_count, row.quantity)
            self.assertEqual(package.step_actual_kg, row.kilos)
            self.assertEqual(package.quant_ids.owner_id, self.producer)
            self.assertAlmostEqual(sum(package.quant_ids.mapped('quantity')), package.step_tag_line_ids.quantity)
            self.assertEqual(package.step_tag_line_ids.boxes, row.quantity)
        self.assertFalse(picking.move_ids.stock_valuation_layer_ids)

    def test_single_tag_validates_400kg_without_package_master(self):
        picking = self.receipt()
        self.assertFalse(picking.fruit_tag_line_ids.package_id)
        picking.button_validate()
        self.assert_received(picking)
        self.assertEqual(picking.move_ids.quantity, 400)
        self.assertEqual(picking.fruit_tag_line_ids.package_id.step_tag_line_ids.quantity, 400)

    def test_two_tags_same_product_native_stock(self):
        picking = self.receipt((160, 240))
        picking.button_validate()
        self.assert_received(picking)
        self.assertEqual(len(picking.move_ids), 1)
        self.assertEqual(len(picking.move_line_ids), 2)
        self.assertEqual(sorted(picking.move_line_ids.mapped('quantity')), [160, 240])

    def test_retry_before_done_and_revalidate_done_are_idempotent(self):
        picking = self.receipt()
        picking._prepare_process_tags()
        package = picking.fruit_tag_line_ids.package_id
        picking._prepare_process_tags()
        self.assertEqual(picking.fruit_tag_line_ids.package_id, package)
        picking.button_validate()
        picking.button_validate()
        self.assertEqual(len(package.step_tag_line_ids), 1)
        self.assertEqual(sum(package.quant_ids.mapped('quantity')), 400)

    def test_premature_legacy_validation_recovers_only_unreceived_tag(self):
        picking = self.receipt()
        row = picking.fruit_tag_line_ids
        package = self.env['stock.quant.package'].create({
            'name': row.tag_number, 'is_fruit_tag': True, 'step_tag_kind': 'C',
            'step_producer_id': self.producer.id, 'step_tag_line_ids': [(0, 0, {
                'producer_id': self.producer.id, 'product_id': self.product.id,
                'quantity': 50, 'kilos': 400, 'boxes': 50})]})
        package.action_step_validate_tag()
        row.package_id = package
        picking.button_validate()
        self.assert_received(picking)
        self.assertEqual(row.package_id, package)
        self.assertEqual(package.step_tag_line_ids.quantity, 400)

    def test_used_tag_rejected_without_changes(self):
        first = self.receipt(); first.button_validate()
        package = first.fruit_tag_line_ids.package_id
        second = self.receipt(); second.fruit_tag_line_ids.tag_number = package.name
        with self.assertRaises(ValidationError):
            second.button_validate()
        self.assertEqual(second.state, 'assigned')
        self.assertFalse(second.fruit_tag_line_ids.package_id)
        self.assertEqual(sum(package.quant_ids.mapped('quantity')), 400)

    def test_weight_failure_rolls_back_created_package_and_details(self):
        picking = self.receipt()
        picking.step_fruit_gross_kg = 401
        name = picking.fruit_tag_line_ids.tag_number
        with self.assertRaises(ValidationError):
            picking.button_validate()
        self.assertFalse(self.env['stock.quant.package'].search([('name', '=', name)]))
        self.assertFalse(picking.fruit_tag_line_ids.package_id)
        self.assertEqual(picking.move_ids.quantity, 400)

    def test_duplicate_numbers_and_operation_mismatch_rejected(self):
        picking = self.receipt((160, 240))
        picking.fruit_tag_line_ids[1].tag_number = picking.fruit_tag_line_ids[0].tag_number
        with self.assertRaises(ValidationError):
            picking.button_validate()
        picking.fruit_tag_line_ids[1].tag_number += '-B'
        picking.move_ids.quantity = 399
        with self.assertRaises(ValidationError):
            picking.button_validate()
        self.assertFalse(picking.fruit_tag_line_ids.package_id)

    def test_existing_lot_is_preserved(self):
        self.product.tracking = 'lot'
        picking = self.receipt()
        lot = self.env['stock.lot'].create({'name': 'QA120-L', 'product_id': self.product.id,
                                          'company_id': self.env.company.id})
        picking.move_line_ids.lot_id = lot
        picking.button_validate()
        self.assert_received(picking)
        self.assertEqual(picking.move_line_ids.lot_id, lot)

    def test_native_backorder_keeps_remaining_demand_without_old_tags(self):
        picking = self.receipt((160,), demand=400)
        action = picking.button_validate()
        self.assertEqual(action['res_model'], 'stock.backorder.confirmation')
        wizard = self.env[action['res_model']].with_context(action['context']).create({})
        wizard.process()
        self.assert_received(picking)
        backorder = self.env['stock.picking'].search([('backorder_id', '=', picking.id)])
        self.assertEqual(backorder.move_ids.product_uom_qty, 240)
        self.assertFalse(backorder.fruit_tag_line_ids)
        self.assertEqual(backorder.step_fruit_gross_kg, 0)

    def test_unit_products_use_packaging_conversion(self):
        product = self.env['product.product'].create({'name': 'QA120 unidad', 'is_storable': True})
        packaging = self.env['product.packaging'].create({'name': 'QA120 caja unidad',
                                                        'product_id': product.id, 'qty': 1})
        picking = self.receipt(product=product, packaging=packaging, demand=50)
        picking.button_validate()
        self.assert_received(picking)
        self.assertEqual(picking.move_ids.quantity, 50)
        self.assertEqual(picking.fruit_tag_line_ids.package_id.step_actual_kg, 400)

    def test_form_hides_manual_package_and_container_section(self):
        view = self.env.ref('step_packing_reception_revision.view_process_reception_form')
        arch = etree.fromstring(self.env['stock.picking'].get_view(view_id=view.id, view_type='form')['arch'])
        self.assertEqual(arch.xpath("//field[@name='fruit_tag_line_ids']/list/field[@name='package_id']/@column_invisible"), ['True'])
        self.assertEqual(arch.xpath("//field[@name='step_container_transfer_ids']/@invisible"), ['1'])
        self.assertEqual(arch.xpath("//button[@name='action_prepare_fruit_stock']/@invisible"), ['1'])
