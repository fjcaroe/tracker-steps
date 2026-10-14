# -*- coding: utf-8 -*-
from ast import literal_eval

from odoo import Command
from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install', 'step_packing')
class TestPackingFruta(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.stock_user = cls.env['res.users'].create({
            'name': 'Operador Packing Fruta',
            'login': 'packing_fruta_test_user',
            'groups_id': [Command.set([
                cls.env.ref('base.group_user').id,
                cls.env.ref('stock.group_stock_user').id,
                cls.env.ref('mrp.group_mrp_user').id,
            ])],
        })
        cls.plain_user = cls.env['res.users'].create({
            'name': 'Usuario sin inventario',
            'login': 'packing_fruta_plain_user',
            'groups_id': [Command.set([cls.env.ref('base.group_user').id])],
        })
        cls.species = cls.env['step.especie'].create({
            'name': 'Cereza prueba T34', 'type_especie': 'frutal', 'group_especie': 'fruta_h'})
        cls.variety_group = cls.env['step.grupo.variedad'].create({
            'name': 'Rojas prueba T34', 'especie_id': cls.species.id})
        cls.variety = cls.env['step.variedad'].create({
            'name': 'Lapins prueba T34', 'cod_variedad': 'T34LAP', 'especie_id': cls.species.id,
            'grupo_variedad_id': cls.variety_group.id,
        })
        cls.fundo = cls.env['step.fundo'].create({'name': 'Fundo prueba T34'})
        cls.category = cls.env['step.packing.fruit.category'].create({'name': 'Exportación T34'})
        cls.caliber = cls.env['step.packing.fruit.caliber'].create({'name': 'XL T34'})
        cls.product = cls.env['product.product'].create({'name': 'Cereza granel T34', 'is_storable': True})
        cls.incoming_type = cls.env['stock.picking.type'].search([
            ('code', '=', 'incoming'), ('company_id', '=', cls.env.company.id)], limit=1)
        cls.outgoing_type = cls.env['stock.picking.type'].search([
            ('code', '=', 'outgoing'), ('company_id', '=', cls.env.company.id)], limit=1)

    def _reception_vals(self):
        return {
            'picking_type_id': self.incoming_type.id,
            'location_id': self.env.ref('stock.stock_location_suppliers').id,
            'location_dest_id': self.incoming_type.default_location_dest_id.id,
            'fruit_fundo_id': self.fundo.id,
            'fruit_species_id': self.species.id,
            'fruit_variety_id': self.variety.id,
            'fruit_category_id': self.category.id,
            'fruit_lot': 'L-T34-001',
            'fruit_harvest_date': '2026-09-27',
            'fruit_guide_number': '123456',
            'fruit_freight_paid': True,
            'fruit_truck_plate': 'AB-CD-12',
            'fruit_freight_rate': 45000.0,
            'move_ids': [Command.create({
                'name': self.product.name,
                'product_id': self.product.id,
                'product_uom_qty': 500.0,
                'product_uom': self.product.uom_id.id,
                'location_id': self.env.ref('stock.stock_location_suppliers').id,
                'location_dest_id': self.incoming_type.default_location_dest_id.id,
            })],
            'fruit_tag_line_ids': [
                Command.create({'tag_number': 'T-1', 'caliber_id': self.caliber.id,
                                'category_id': self.category.id, 'quantity': 50, 'kilos': 250.0}),
                Command.create({'tag_number': 'T-2', 'caliber_id': self.caliber.id,
                                'category_id': self.category.id, 'quantity': 50, 'kilos': 250.0}),
            ],
        }

    def test_app_menus(self):
        root = self.env.ref('step_packing.menu_packing_fruta_root')
        self.assertFalse(root.parent_id)
        self.assertTrue(root.web_icon_data, 'La app Packing Fruta debe tener ícono')
        self.assertTrue(self.env.ref('step_packing.menu_step_packing_root').web_icon_data)
        reception_menu = self.env.ref('step_packing.menu_step_packing_reception')
        self.assertEqual(reception_menu.parent_id, self.env.ref('step_packing.menu_packing_fruta_receptions'))
        for xmlid in ('step_packing.menu_packing_fruta_reception', 'step_packing.menu_packing_fruta_production',
                      'step_packing.menu_packing_fruta_stock_move', 'step_packing.menu_packing_fruta_dispatch',
                      'step_packing.menu_packing_fruta_inspection_sag', 'step_packing.menu_packing_fruta_fundo',
                      'step_packing.menu_packing_fruta_variety', 'step_packing.menu_packing_fruta_labor'):
            menu = self.env.ref(xmlid)
            self.assertTrue(menu.action, xmlid)
            self.assertEqual(menu._get_full_name().split('/')[0], 'Packing Fruta', xmlid)

    def test_menus_visible_by_role(self):
        visible = self.env['ir.ui.menu'].with_user(self.stock_user)._visible_menu_ids()
        self.assertIn(self.env.ref('step_packing.menu_packing_fruta_root').id, visible)
        self.assertIn(self.env.ref('step_packing.menu_packing_fruta_reception').id, visible)
        self.assertIn(self.env.ref('step_packing.menu_packing_fruta_production').id, visible)
        plain = self.env['ir.ui.menu'].with_user(self.plain_user)._visible_menu_ids()
        self.assertIn(self.env.ref('step_packing.menu_packing_fruta_root').id, plain)
        self.assertNotIn(self.env.ref('step_packing.menu_packing_fruta_reception').id, plain)
        self.assertNotIn(self.env.ref('step_packing.menu_packing_fruta_production').id, plain)

    def test_fruit_reception_flow(self):
        picking = self.env['stock.picking'].with_user(self.stock_user).create(self._reception_vals())
        self.assertEqual(picking.picking_type_code, 'incoming')
        self.assertEqual(len(picking.fruit_tag_line_ids), 2)
        self.assertEqual(sum(picking.fruit_tag_line_ids.mapped('kilos')), 500.0)
        self.assertEqual(picking.fruit_tag_line_ids.company_id, picking.company_id)
        picking.action_confirm()
        picking.move_ids.quantity = 500.0
        picking.button_validate()
        self.assertEqual(picking.state, 'done')
        self.assertEqual(picking.fruit_lot, 'L-T34-001')

        action = self.env.ref('step_packing.action_step_packing_fruit_reception')
        domain = literal_eval(action.domain)
        found = self.env['stock.picking'].with_user(self.stock_user).search(domain + [('fruit_lot', '=', 'L-T34-001')])
        self.assertEqual(found, picking)
        dispatch_domain = literal_eval(self.env.ref('step_packing.action_step_packing_fruit_dispatch').domain)
        self.assertFalse(self.env['stock.picking'].search(dispatch_domain + [('id', '=', picking.id)]))

    def test_tag_lines_follow_picking(self):
        picking = self.env['stock.picking'].create(self._reception_vals())
        lines = picking.fruit_tag_line_ids
        copy = picking.copy()
        self.assertEqual(len(copy.fruit_tag_line_ids), 2)
        picking.unlink()
        self.assertFalse(lines.exists())

    def test_plain_user_cannot_read_pickings(self):
        picking = self.env['stock.picking'].create(self._reception_vals())
        with self.assertRaises(AccessError):
            picking.with_user(self.plain_user).read(['fruit_lot'])

    def test_production_fruit_data(self):
        production = self.env['mrp.production'].with_user(self.stock_user).create({
            'product_id': self.product.id,
            'product_qty': 10.0,
            'product_uom_id': self.product.uom_id.id,
            'fruit_species_id': self.species.id,
            'fruit_variety_id': self.variety.id,
            'fruit_fundo_id': self.fundo.id,
            'fruit_shift': 'Día',
            'fruit_shipment_ref': 'EMB-T34',
        })
        self.assertEqual(production.fruit_variety_id, self.variety)
        self.assertEqual(production.fruit_shipment_ref, 'EMB-T34')

    def test_views_render(self):
        for model, view_ref in (
            ('stock.picking', 'stock.view_picking_form'),
            ('stock.picking', 'step_packing.view_picking_list_packing_fruit'),
            ('mrp.production', 'mrp.mrp_production_form_view'),
        ):
            view = self.env.ref(view_ref)
            arch = self.env[model].with_user(self.stock_user).get_view(view.id)['arch']
            self.assertIn('fruit_', arch, view_ref)

    def test_default_stages(self):
        campo = self.env['step.packing.campo'].create({'name': 'Proceso campo T34'})
        self.assertEqual(campo.stage_id, self.env.ref('step_packing.stage_packing_campo_new'))
        reception = self.env['step.packing.reception'].create({'name': 'Granel T34'})
        self.assertEqual(reception.stage_id, self.env.ref('step_packing.stage_packing_reception_new'))
        self.assertEqual(
            self.env['step.packing.campo.stage'].search([]).mapped('name')[:3], ['Nuevo', 'En progreso', 'Listo'])
