from lxml import etree
from odoo.tests import TransactionCase, Form, tagged
from odoo.exceptions import UserError, ValidationError


@tagged('post_install', '-at_install')
class PackingStockFlowCase(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.source_wh = cls.env['stock.warehouse'].search([('company_id', '=', cls.company.id)], limit=1)
        cls.wh = cls.env['stock.warehouse'].create({'name': 'QA T121 Packing', 'code': 'QT121', 'company_id': cls.company.id})
        cls.company.write({'step_packing_warehouse_id': cls.wh.id,
                           'step_packing_fruit_location_id': cls.wh.lot_stock_id.id,
                           'step_packing_material_location_id': cls.wh.lot_stock_id.id,
                           'step_packing_require_contract': False})
        cls.producer = cls.env['res.partner'].create({'name': 'QA T121 productor'})
        cls.species = cls.env['step.especie'].create({'name': 'QA T121 especie', 'type_especie': 'frutal', 'group_especie': 'fruta_h'})
        group = cls.env['step.grupo.variedad'].create({'name': 'QA T121 grupo', 'especie_id': cls.species.id})
        cls.variety = cls.env['step.variedad'].create({'name': 'QA T121 variedad', 'cod_variedad': 'QT121',
                                                     'especie_id': cls.species.id, 'grupo_variedad_id': group.id})
        cls.raw = cls.env['product.product'].create({'name': 'QA T121 fruta', 'is_storable': True})
        cls.finished = cls.env['product.product'].create({'name': 'QA T121 caja fruta', 'is_storable': True})
        cls.national = cls.env['product.product'].create({'name': 'QA T121 nacional', 'is_storable': True})
        cls.material = cls.env['product.product'].create({'name': 'QA T121 cartón', 'is_storable': True})
        cls.env['mrp.bom'].create({'product_tmpl_id': cls.finished.product_tmpl_id.id, 'product_qty': 1,
                                 'bom_line_ids': [(0, 0, {'product_id': cls.material.id, 'product_qty': 1,
                                                        'step_export_qty_per_pallet': 2})]})

    def tag(self, kind, product, quantity, kilos, result=False):
        return self.env['stock.quant.package'].create({
            'name': self.env['ir.sequence'].next_by_code('stock.quant.package'), 'is_fruit_tag': True,
            'step_tag_kind': kind, 'step_packing_result': result, 'step_producer_id': self.producer.id,
            'especie_id': self.species.id, 'variedad_id': self.variety.id,
            'step_tag_line_ids': [(0, 0, {'product_id': product.id, 'producer_id': self.producer.id,
                                         'quantity': quantity, 'boxes': quantity, 'kilos': kilos})]})

    def ot(self, material_qty=18):
        incoming = self.tag('C', self.raw, 100, 100)
        incoming.action_step_validate_tag()
        self.env['stock.quant']._update_available_quantity(self.raw, self.source_wh.lot_stock_id, 100,
                                                          package_id=incoming, owner_id=self.producer)
        finished = self.tag('E', self.finished, 16, 80, 'export')
        national = self.tag('N', self.national, 15, 15, 'commercial')
        if material_qty:
            self.env['stock.quant']._update_available_quantity(self.material, self.wh.lot_stock_id, material_qty)
        return self.env['step.packing.production'].create({
            'step_packing_input_tag_ids': [(6, 0, incoming.ids)],
            'step_packing_output_tag_ids': [(6, 0, (finished | national).ids)]})

    def approve(self, ot):
        ot.action_prepare_materials(); ot.action_approve_materials()

    def test_validation_transfers_exact_package_and_producer_then_close_consumes(self):
        ot = self.ot()
        ot.action_step_packing_validate()
        transfer = ot.step_packing_transfer_id
        self.assertEqual(transfer.state, 'done')
        self.assertEqual(transfer.picking_type_id, self.wh.int_type_id)
        self.assertEqual(transfer.location_id, self.source_wh.lot_stock_id)
        self.assertEqual(transfer.location_dest_id, self.wh.lot_stock_id)
        self.assertEqual(transfer.move_line_ids.package_id, ot.step_packing_input_tag_ids)
        self.assertEqual(transfer.move_line_ids.result_package_id, ot.step_packing_input_tag_ids)
        self.assertEqual(transfer.move_line_ids.owner_id, self.producer)
        ot._transfer_fruit_to_packing()
        self.assertEqual(ot.step_packing_transfer_id, transfer)
        self.approve(ot)
        ot.action_step_packing_close()
        self.assertEqual(ot.state, 'closed')
        self.assertEqual(ot.material_picking_id.location_id, self.wh.lot_stock_id)
        self.assertEqual(ot.input_picking_id.location_id, self.wh.lot_stock_id)
        self.assertEqual(ot.output_picking_id.location_dest_id, self.wh.lot_stock_id)
        self.assertEqual(ot.step_packing_input_tag_ids.step_tag_state, 'processed')
        self.assertEqual(ot.material_picking_id.move_ids.quantity, 18)
        self.assertFalse(ot.input_picking_id.move_ids.stock_valuation_layer_ids)
        national = ot.step_packing_output_tag_ids.filtered(lambda t: t.step_tag_kind == 'N')
        self.assertEqual(national.quant_ids.filtered(lambda q: q.quantity > 0).owner_id, self.producer)
        with self.assertRaises(UserError):
            ot.action_step_packing_close()

    def test_shortage_in_configured_source_does_not_use_other_warehouse(self):
        ot = self.ot(material_qty=1)
        self.env['stock.quant']._update_available_quantity(self.material, self.source_wh.lot_stock_id, 500)
        ot.action_step_packing_validate(); self.approve(ot)
        with self.assertRaisesRegex(UserError, self.wh.code):
            ot.action_step_packing_close()
        self.assertEqual(ot.state, 'validated')
        self.assertFalse(ot.material_picking_id or ot.input_picking_id or ot.output_picking_id)
        qty = self.env['stock.quant']._get_available_quantity(self.material, self.wh.lot_stock_id)
        self.assertEqual(qty, 1)

    def test_legacy_validated_ot_moves_only_when_close_succeeds(self):
        ot = self.ot(material_qty=1)
        self.company.write({'step_packing_warehouse_id': False, 'step_packing_fruit_location_id': False,
                            'step_packing_material_location_id': False})
        ot.action_step_packing_validate(); self.approve(ot)
        self.company.write({'step_packing_warehouse_id': self.wh.id,
                            'step_packing_fruit_location_id': self.wh.lot_stock_id.id,
                            'step_packing_material_location_id': self.wh.lot_stock_id.id})
        with self.assertRaises(UserError):ot.action_step_packing_close()
        self.assertFalse(ot.step_packing_transfer_id)
        positive = ot.step_packing_input_tag_ids.quant_ids.filtered(lambda q: q.quantity > 0)
        self.assertEqual(positive.location_id, self.source_wh.lot_stock_id)
        self.env['stock.quant']._update_available_quantity(self.material, self.wh.lot_stock_id, 17)
        ot.action_step_packing_close()
        self.assertEqual(ot.state, 'closed')
        self.assertEqual(ot.step_packing_transfer_id.state, 'done')

    def test_reserved_raw_fruit_cannot_be_transferred(self):
        ot = self.ot()
        quant = ot.step_packing_input_tag_ids.quant_ids.filtered(lambda q: q.quantity > 0)
        quant.reserved_quantity = 1
        with self.assertRaises(UserError):ot.action_step_packing_validate()
        self.assertEqual(ot.state, 'created')
        self.assertFalse(ot.step_packing_transfer_id)

    def test_company_owned_materials_only(self):
        ot = self.ot(material_qty=0)
        self.env['stock.quant']._update_available_quantity(self.material, self.wh.lot_stock_id, 100, owner_id=self.producer)
        ot.action_step_packing_validate(); self.approve(ot)
        with self.assertRaises(UserError):ot.action_step_packing_close()
        self.assertEqual(ot.state, 'validated')

    def test_non_inventory_fruit_is_rejected_before_moving_any_package(self):
        self.national.is_storable = False
        ot = self.ot()
        with self.assertRaisesRegex(UserError, 'controlar inventario'):
            ot.action_step_packing_validate()
        self.assertEqual(ot.state, 'created')
        self.assertFalse(ot.step_packing_transfer_id)
        self.assertEqual(ot.step_packing_input_tag_ids.quant_ids.filtered(lambda q: q.quantity > 0).location_id,
                         self.source_wh.lot_stock_id)

    def test_exact_lots_survive_fruit_transfer_and_material_consumption(self):
        self.raw.tracking = 'lot'; self.material.tracking = 'lot'
        ot = self.ot(material_qty=0)
        raw_lot = self.env['stock.lot'].create({'name': 'QA121-RAW', 'product_id': self.raw.id, 'company_id': self.company.id})
        ot.step_packing_input_tag_ids.quant_ids.lot_id = raw_lot
        lots = self.env['stock.lot']
        for name, quantity in [('QA121-A', 10), ('QA121-B', 8)]:
            lot = self.env['stock.lot'].create({'name': name, 'product_id': self.material.id, 'company_id': self.company.id})
            self.env['stock.quant']._update_available_quantity(self.material, self.wh.lot_stock_id, quantity, lot_id=lot)
            lots |= lot
        ot.action_step_packing_validate(); self.approve(ot); ot.action_step_packing_close()
        self.assertEqual(ot.step_packing_transfer_id.move_line_ids.lot_id, raw_lot)
        self.assertEqual(ot.input_picking_id.move_line_ids.lot_id, raw_lot)
        self.assertEqual(ot.material_picking_id.move_line_ids.lot_id, lots)
        self.assertEqual(sorted(ot.material_picking_id.move_line_ids.mapped('quantity')), [8, 10])

    def test_material_source_can_differ_from_fruit_staging(self):
        child = self.env['stock.location'].create({'name': 'QA121 materiales', 'usage': 'internal',
                                                   'company_id': self.company.id, 'location_id': self.wh.lot_stock_id.id})
        self.company.step_packing_material_location_id = child
        ot = self.ot(material_qty=0)
        self.env['stock.quant']._update_available_quantity(self.material, child, 18)
        ot.action_step_packing_validate(); self.approve(ot); ot.action_step_packing_close()
        self.assertEqual(ot.material_picking_id.location_id, child)
        self.assertEqual(ot.input_picking_id.location_id, self.wh.lot_stock_id)

    def test_foreign_or_external_locations_are_rejected(self):
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self.company.step_packing_material_location_id = self.source_wh.lot_stock_id
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self.company.step_packing_material_location_id = self.env.ref('stock.stock_location_suppliers')

    def test_configuration_is_idempotent_and_does_not_move_stock(self):
        self.company.write({'step_packing_warehouse_id': False, 'step_packing_fruit_location_id': False,
                            'step_packing_material_location_id': False})
        quant_count = self.env['stock.quant'].search_count([])
        move_count = self.env['stock.move'].search_count([])
        configured = self.company._configure_packing_warehouse()
        self.assertEqual(self.company._configure_packing_warehouse(), configured)
        self.assertEqual(self.env['stock.quant'].search_count([]), quant_count)
        self.assertEqual(self.env['stock.move'].search_count([]), move_count)

    def test_native_form_exposes_sources_and_transfer_is_protected(self):
        ot = self.ot()
        view = self.env.ref('step_packing_operations.view_packing_production_form')
        arch = etree.fromstring(ot.get_view(view_id=view.id, view_type='form')['arch'])
        self.assertTrue(arch.xpath("//page[@name='packing_stock_flow']//field[@name='step_stock_material_location_id']"))
        Form(ot, view=view)
        Form(self.company, view='step_packing_stock_flow.packing_company_form')
        with self.assertRaises(UserError):ot.step_packing_transfer_id = self.env['stock.picking'].create({
            'picking_type_id': self.wh.int_type_id.id, 'location_id': self.wh.lot_stock_id.id,
            'location_dest_id': self.source_wh.lot_stock_id.id})
