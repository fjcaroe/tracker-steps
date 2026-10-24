from datetime import timedelta
from lxml import etree
from odoo import fields
from odoo.tests import Form, TransactionCase, tagged
from odoo.exceptions import ValidationError
from ..hooks import post_init_hook


VIEW = 'step_packing_reception_revision.view_process_reception_form'
ORDER = ['product_id', 'step_fruit_pallet_type_id', 'step_fruit_pallet_qty',
         'product_packaging_id', 'step_fruit_packaging_qty', 'product_uom', 'product_uom_qty']


@tagged('post_install', '-at_install')
class ReceptionCase(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.company.step_fruit_inventory_enabled = True
        cls.warehouse = cls.env['stock.warehouse'].search([('company_id', '=', cls.env.company.id)], limit=1)
        cls.producer = cls.env['res.partner'].create({'name': 'QA T118 productor', 'is_productor': True})
        cls.other = cls.env['res.partner'].create({'name': 'QA T118 otro productor', 'is_productor': True})
        cls.product = cls.env['product.product'].create({'name': 'QA T118 fruta', 'is_storable': True})
        cls.packaging = cls.env['product.packaging'].create({'name': 'QA T118 caja', 'product_id': cls.product.id, 'qty': 8})
        cls.pallet = cls.env['stock.package.type'].create({'name': 'QA T118 pallet'})

    def picking(self):
        wh = self.warehouse
        return self.env['stock.picking'].create({'partner_id': self.producer.id,
            'picking_type_id': wh.in_type_id.id, 'location_id': wh.in_type_id.default_location_src_id.id,
            'location_dest_id': wh.lot_stock_id.id, 'step_fruit_reception_kind': 'process'})

    def contract(self, **values):
        today = fields.Date.today()
        return self.env['step.producer.purchase.contract'].create(dict({
            'partner_id': self.producer.id, 'state': 'confirmed',
            'date_start': today-timedelta(days=1), 'date_end': today+timedelta(days=1)}, **values))

    def test_effective_form_and_original_form_are_separate(self):
        model = self.env['stock.picking']
        arch = etree.fromstring(model.get_view(view_id=self.env.ref(VIEW).id, view_type='form')['arch'])
        columns = arch.xpath("//field[@name='move_ids_without_package']/list/field/@name")
        start = columns.index('product_id')
        self.assertEqual(columns[start:start+7], ORDER)
        self.assertTrue(arch.xpath("//page[@name='step_fruit_freights']//field[@name='fruit_freight_paid']"))
        self.assertFalse(arch.xpath("//page[@name='step_packing_fruit']//field[@name='fruit_freight_paid']"))
        for old in ('fruit_class_id', 'fruit_weighing_type', 'fruit_grower_contract'):
            self.assertFalse(arch.xpath("//page[@name='step_packing_fruit']//field[@name='%s']" % old))
        guide = arch.xpath("//page[@name='step_packing_fruit']//field[@name='fruit_guide_number']")[0]
        self.assertEqual(guide.getnext().get('name'), 'step_fruit_guide_date')
        self.assertTrue(arch.xpath("//field[@name='step_fruit_contract_id']/@domain"))
        original = etree.fromstring(model.get_view(view_id=self.env.ref('stock.view_picking_form').id, view_type='form')['arch'])
        self.assertFalse(original.xpath("//field[@name='step_fruit_contract_id']"))
        action = self.env.ref('step_inventory_packing.action_steps_fruit_process_reception')
        self.assertIn(self.env.ref(VIEW), action.view_ids.mapped('view_id'))
        Form(self.picking(), view=VIEW)

    def test_contract_scope_and_single_candidate_onchange(self):
        valid = self.contract()
        self.contract(state='draft')
        self.contract(partner_id=self.other.id)
        self.contract(date_start=fields.Date.today()-timedelta(days=5), date_end=fields.Date.today()-timedelta(days=2))
        picking = self.picking()
        self.assertEqual(self.env['step.producer.purchase.contract'].search(picking._fruit_contract_domain()), valid)
        with Form(picking, view=VIEW) as form:
            form.partner_id = self.other
            form.partner_id = self.producer
            self.assertEqual(form.step_fruit_contract_id, valid)
        self.assertEqual(picking.step_fruit_contract_id, valid)
        with self.assertRaises(ValidationError), self.cr.savepoint():
            picking.step_fruit_contract_id = self.contract(partner_id=self.other.id)

    def test_multiple_contracts_are_not_chosen_arbitrarily(self):
        self.contract(); self.contract()
        picking = self.picking()
        picking._onchange_fruit_contract()
        self.assertFalse(picking.step_fruit_contract_id)
        picking.partner_id = self.other
        picking._onchange_fruit_contract()
        self.assertFalse(picking.step_fruit_contract_id)

    def test_operations_count_updates_native_quantity_not_demand(self):
        picking = self.picking()
        move = self.env['stock.move'].create({'name': 'QA T118 movimiento', 'picking_id': picking.id,
            'product_id': self.product.id, 'product_uom': self.product.uom_id.id, 'product_uom_qty': 80,
            'location_id': picking.location_id.id, 'location_dest_id': picking.location_dest_id.id,
            'product_packaging_id': self.packaging.id})
        with Form(picking, view=VIEW) as form:
            with form.move_ids_without_package.edit(0) as line:
                line.step_fruit_pallet_type_id = self.pallet
                line.step_fruit_pallet_qty = 2
                line.step_fruit_packaging_qty = 10
        self.env.flush_all(); move.invalidate_recordset()
        self.assertEqual(move.quantity, 80)
        self.assertEqual(move.product_packaging_quantity, 10)
        self.assertEqual(move.step_fruit_packaging_qty, 10)
        self.assertEqual(move.step_fruit_pallet_type_id, self.pallet)
        self.assertEqual(move.step_fruit_pallet_qty, 2)
        self.assertEqual(move.product_uom_qty, 80)
        with self.assertRaises(ValidationError), self.cr.savepoint():
            move.step_fruit_pallet_qty = -1

    def test_class_migration_requires_unique_existing_master(self):
        category = self.env['step.management.fruit.category'].create({'code': 'QA118', 'name': 'QA T118 categoría'})
        fruit_class = self.env['step.management.fruit.class'].create({'code': 'QA118A', 'name': 'QA T118 clase', 'category_id': category.id})
        picking = self.picking(); picking.fruit_class_id = category
        self.env.flush_all(); post_init_hook(self.env); picking.invalidate_recordset()
        self.assertEqual(picking.step_fruit_origin_class_id, fruit_class)
        self.assertEqual(picking.fruit_class_id, category)
        self.env['step.management.fruit.class'].create({'code': 'QA118B', 'name': 'QA T118 otra clase', 'category_id': category.id})
        picking.step_fruit_origin_class_id = False
        self.env.flush_all(); post_init_hook(self.env); picking.invalidate_recordset()
        self.assertFalse(picking.step_fruit_origin_class_id)
        self.assertEqual(picking.fruit_class_id, category)

    def test_contract_date_uses_the_operating_timezone(self):
        picking = self.picking().with_context(tz='America/Santiago')
        picking.scheduled_date = '2026-10-24 01:00:00'
        self.assertEqual(str(picking.step_fruit_contract_date), '2026-10-23')

    def test_fruit_selector_and_historical_text_preservation(self):
        picking = self.picking()
        picking.fruit_type = 'Orgánica'
        self.env.flush_all(); post_init_hook(self.env); picking.invalidate_recordset()
        self.assertEqual(picking.step_fruit_type, 'organic')
        self.assertEqual(picking.fruit_type, 'Orgánica')
        with Form(picking, view=VIEW) as form:
            form.step_fruit_type = 'conventional'
        self.assertEqual(picking.step_fruit_type, 'conventional')
        self.assertEqual(picking.fruit_type, 'Orgánica')
        picking.write({'fruit_type': 'clasificación histórica sin equivalencia', 'step_fruit_type': False})
        self.env.flush_all(); post_init_hook(self.env); picking.invalidate_recordset()
        self.assertFalse(picking.step_fruit_type)
        self.assertEqual(picking.fruit_type, 'clasificación histórica sin equivalencia')
        choices = dict(self.env['stock.picking']._fields['step_fruit_type']._description_selection(self.env))
        self.assertEqual(set(choices), {'conventional', 'organic'})
