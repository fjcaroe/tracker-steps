from odoo import Command
from odoo.exceptions import AccessError, ValidationError, UserError
from odoo.tests import TransactionCase, Form, tagged, new_test_user


@tagged('post_install', '-at_install')
class TestMasters(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.a = cls.env.company
        cls.b = cls.env['res.company'].create({'name': 'QA shared branch', 'parent_id': cls.a.id})
        cls.c = cls.env['res.company'].create({'name': 'QA unrelated company'})
        cls.user = new_test_user(cls.env, login='qa-shared-master',
            groups='base.group_user,base.group_erp_manager,base.group_multi_company,stock.group_stock_manager,step_management_costs.group_management_manager,sales_team.group_sale_manager',
            company_id=cls.a.id, company_ids=[Command.set((cls.a | cls.b).ids)])
        cls.models = ('step.fundo', 'step.management.fruit.category', 'step.management.fruit.quality', 'step.fruit.color')
        cls.category = cls.env['step.management.fruit.category'].create({'name': 'QA shared category', 'code': 'QA-MC-C',
            'company_id': cls.a.id, 'company_ids': [Command.set((cls.a | cls.b).ids)]})

    def make(self, model, **values):
        vals = {'name': 'QA shared master', 'company_id': self.a.id}
        if 'code' in self.env[model]._fields:
            vals['code'] = 'QA-MC-X'
        vals.update(values)
        return self.env[model].create(vals)

    def test_original_company_default(self):
        for name in self.models:
            record = self.make(name)
            self.assertEqual(record.company_ids, self.a)

    def test_all_five_shared_across_branch(self):
        for name in (*self.models, 'step.management.fruit.class'):
            vals = {'company_ids': [Command.set((self.a | self.b).ids)]}
            if name.endswith('.class'):
                vals['category_id'] = self.category.id
            record = self.make(name, **vals)
            branch = record.with_user(self.user).with_context(allowed_company_ids=self.b.ids)
            self.assertIn(record.id, branch.search([('id', '=', record.id)]).ids)
            branch.read(['name', 'company_ids'])
            branch.write({'name': 'QA edited from branch'})
            self.assertEqual(record.company_id, self.a)

    def test_unselected_company_cannot_read(self):
        record = self.make('step.fruit.color')
        user = new_test_user(self.env, login='qa-foreign-master', groups='sales_team.group_sale_manager',
                             company_id=self.c.id, company_ids=[Command.set(self.c.ids)])
        other = record.with_user(user).with_context(allowed_company_ids=self.c.ids)
        self.assertFalse(other.search([('id', '=', record.id)]))
        with self.assertRaises(AccessError):
            other.read(['name'])

    def test_empty_and_original_removal_rejected(self):
        record = self.make('step.fundo')
        for companies in ([], self.b.ids):
            with self.assertRaises(ValidationError), self.cr.savepoint():
                record.write({'company_ids': [Command.set(companies)]})

    def test_unauthorized_company_assignment_rejected(self):
        model = self.env['step.fruit.color'].with_user(self.user).with_context(allowed_company_ids=(self.a | self.b).ids)
        with self.assertRaises(AccessError), self.cr.savepoint():
            model.create({'name': 'QA forbidden', 'code': 'QA-FORBIDDEN', 'company_ids': [Command.set((self.a | self.c).ids)]})
        record = self.make('step.fruit.color')
        with self.assertRaises(AccessError), self.cr.savepoint():
            record.with_env(model.env).write({'company_ids': [Command.set((self.a | self.c).ids)]})

    def test_overlapping_codes_rejected(self):
        self.make('step.fruit.color')
        second = self.make('step.fruit.color', company_id=self.b.id)
        with self.assertRaises(ValidationError), self.cr.savepoint():
            second.write({'company_ids': [Command.set((self.a | self.b).ids)]})

    def test_category_covers_all_class_companies(self):
        fruit_class = self.make('step.management.fruit.class', category_id=self.category.id,
                               company_ids=[Command.set((self.a | self.b).ids)])
        with self.assertRaises(ValidationError), self.cr.savepoint():
            fruit_class.write({'company_ids': [Command.set((self.a | self.b | self.c).ids)]})
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self.category.write({'company_ids': [Command.set(self.a.ids)]})

    def test_native_picking_consistency(self):
        warehouse = self.env['stock.warehouse'].search([('company_id', '=', self.b.id)], limit=1)
        self.assertTrue(warehouse)
        pick = self.env['stock.picking'].with_company(self.b).create({'picking_type_id': warehouse.in_type_id.id,
            'location_id': self.env.ref('stock.stock_location_suppliers').id,
            'location_dest_id': warehouse.lot_stock_id.id, 'fruit_category_id': self.category.id})
        pick._check_company(['fruit_category_id'])
        self.assertEqual(pick.company_id, self.b)
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self.category.write({'company_ids': [Command.set(self.a.ids)]})
        foreign = self.make('step.management.fruit.category', code='QA-FOREIGN-CAT', company_id=self.c.id)
        with self.assertRaises(UserError), self.cr.savepoint():
            pick.write({'fruit_category_id': foreign.id})

    def test_native_fundo_form_and_menu(self):
        model = self.env['step.fundo'].with_user(self.user).with_context(allowed_company_ids=(self.a | self.b).ids)
        with Form(model, view='step_hr.view_step_fundo_form') as form:
            form.name = 'QA native shared fundo'
            form.company_ids.add(self.b)
        self.assertEqual(set(form.record.company_ids.ids), set((self.a | self.b).ids))
        menu = self.env.ref('step_agriculture_multicompany.packing_fundos')
        self.assertEqual(menu.action, self.env.ref('step_producers.action_step_producers_fundo'))
        self.assertEqual(menu.parent_id, self.env.ref('step_packing_operations.menu_packing_operations_masters'))

    def test_origin_is_preserved(self):
        record = self.make('step.fundo')
        with self.assertRaises(ValidationError), self.cr.savepoint():
            record.write({'company_id': self.b.id})

    def test_native_packing_fundo_onchange_and_save(self):
        producer = self.env['res.partner'].create({'name': 'QA shared producer', 'is_productor': True})
        farm = self.make('step.fundo', partner_id=producer.id, company_ids=[Command.set((self.a | self.b).ids)])
        model = self.env['step.packing.production'].with_company(self.b)
        draft = model.new({'company_id': self.b.id, 'fruit_grower_id': producer.id})
        draft._onchange_producer_fundo()
        self.assertEqual(draft.fruit_fundo_id, farm)
        production = model.create({'company_id': self.b.id, 'fruit_grower_id': producer.id, 'fruit_fundo_id': farm.id})
        self.assertEqual(production.fruit_fundo_id, farm)
        foreign = self.make('step.fundo', company_id=self.c.id, partner_id=producer.id)
        with self.assertRaises(ValidationError) as failure, self.cr.savepoint():
            production.write({'fruit_fundo_id': foreign.id})
        for detail in (production.display_name, foreign.display_name, self.b.display_name,
                       production.fields_get(['fruit_fundo_id'], ['string'])['fruit_fundo_id']['string']):
            self.assertIn(detail, str(failure.exception))

    def test_native_shipment_quality_consistency(self):
        quality = self.make('step.management.fruit.quality', company_ids=[Command.set((self.a | self.b).ids)])
        shipment = self.env['step.export.export'].new({'company_id': self.b.id})
        line = self.env['step.export.shipment.line'].new({'shipment_id': shipment, 'quality_id': quality.id})
        line._check_quality_company()
        foreign = self.make('step.management.fruit.quality', company_id=self.c.id)
        line.quality_id = foreign
        with self.assertRaises(ValidationError):
            line._check_quality_company()

    def test_empty_fruit_tag_keeps_stock_company_for_master_validation(self):
        farm = self.make('step.fundo', company_id=self.b.id)
        product = self.env['product.product'].create({'name': 'QA T164 fruit', 'is_storable': True})
        tag = self.env['stock.quant.package'].with_company(self.b).create({
            'name': 'QA T164', 'is_fruit_tag': True, 'step_tag_kind': 'C', 'fundo_id': farm.id,
        })
        warehouse = self.env['stock.warehouse'].search([('company_id', '=', self.b.id)], limit=1)
        order = self.env['step.packing.production'].with_company(self.b).create({'company_id': self.b.id})
        order._create_packing_move(warehouse, self.env.ref('stock.stock_location_suppliers'),
                                   warehouse.lot_stock_id, [(product, 1, False, tag)])
        self.assertEqual(tag.company_id, self.b)
        order._create_packing_move(warehouse, warehouse.lot_stock_id, order._production_location(),
                                   [(product, 1, tag, False)])
        self.assertFalse(any(q.quantity > 0 for q in tag.quant_ids))
        if 'step_packing_company_id' in tag._fields:
            # T185 retains the origin even after the last quant. Verify it
            # first, then simulate a pre-T185 tag to exercise the fallback.
            self.assertEqual(tag.company_id, self.b)
            tag.flush_recordset(['step_packing_company_id'])
            self.cr.execute('UPDATE stock_quant_package SET step_packing_company_id=NULL WHERE id=%s', [tag.id])
            tag.invalidate_recordset(['step_packing_company_id'])
            tag.modified(['step_packing_company_id'])
        self.assertFalse(tag.company_id)
        tag.with_company(self.a)._check_agricultural_masters()

    def test_native_web_read_scope_editor(self):
        record = self.make('step.fruit.color', company_ids=[Command.set((self.a | self.b).ids)])
        scoped = record.with_user(self.user).with_context(allowed_company_ids=self.b.ids)
        result = scoped.web_read({'name': {}, 'company_ids': {'fields': {'display_name': {}}}})
        self.assertEqual({c['id'] for c in result[0]['company_ids']}, set((self.a|self.b).ids))

    def test_operator_view_does_not_read_other_company_names(self):
        from lxml import etree
        user = new_test_user(self.env(context=dict(self.env.context, no_reset_password=True)), login='qa-shared-operator',
            groups='base.group_user,stock.group_stock_manager', company_id=self.b.id, company_ids=[Command.set(self.b.ids)])
        for model in self.models:
            record = self.make(model, company_ids=[Command.set((self.a|self.b).ids)])
            scoped = record.with_user(user).with_context(allowed_company_ids=self.b.ids)
            arch = etree.fromstring(scoped.get_view(view_type='form')['arch'])
            self.assertFalse(arch.xpath("//field[@name='company_ids']"))
            result = scoped.web_read({'name': {}, 'company_id': {'fields': {'display_name': {}}}})
            self.assertEqual(result[0]['id'], record.id)

    def test_receive_fruit_from_explicitly_shared_farm_with_only_destination_active(self):
        self.a.step_fruit_inventory_enabled = True
        producer = self.env['res.partner'].create({
            'name': 'QA T194 producer', 'is_productor': True, 'company_id': self.b.id})
        farm = self.make('step.fundo', company_id=self.b.id, partner_id=producer.id,
                         company_ids=[Command.set((self.a | self.b).ids)])
        private_producer = producer.copy({'name': 'QA T194 private producer'})
        self.make('step.fundo', company_id=self.b.id, partner_id=private_producer.id)
        scoped = self.env(user=self.user, context={**self.env.context, 'allowed_company_ids': self.a.ids})
        self.assertEqual(producer.with_env(scoped).read(['name'])[0]['name'], producer.name)
        self.assertFalse(private_producer.with_env(scoped).has_access('read'))
        self.assertFalse(producer.with_env(scoped).has_access('write'))
        self.assertFalse(producer.with_env(scoped).has_access('unlink'))
        restricted = new_test_user(self.env(context={**self.env.context, 'no_reset_password': True}),
            login='qa-t194-restricted', groups='stock.group_stock_user',
            company_id=self.a.id, company_ids=[Command.set(self.a.ids)])
        self.assertFalse(producer.with_user(restricted).with_context(allowed_company_ids=self.a.ids).has_access('read'))

        warehouse = self.env['stock.warehouse'].search([('company_id', '=', self.a.id)], limit=1)
        operation = warehouse.in_type_id
        if 'auto_batch' in operation._fields:
            operation.write({'auto_batch': True, 'batch_group_by_partner': True})
        kg = self.env.ref('uom.product_uom_kgm')
        species = self.env['step.especie'].create({
            'name': 'QA T194 species', 'type_especie': 'frutal', 'group_especie': 'fruta_h'})
        product = self.env['product.product'].create({
            'name': 'QA T194 fruit', 'is_storable': True, 'uom_id': kg.id, 'uom_po_id': kg.id})
        packaging = self.env['product.packaging'].create({
            'name': 'QA T194 box', 'product_id': product.id, 'qty': 8})
        values = {
            'partner_id': producer.id, 'picking_type_id': operation.id,
            'location_id': operation.default_location_src_id.id, 'location_dest_id': warehouse.lot_stock_id.id,
        }
        with self.assertRaises(UserError), self.cr.savepoint():
            scoped['stock.picking'].create(values).action_confirm()
        values.update({
            'step_fruit_reception_kind': 'process', 'fruit_fundo_id': farm.id,
            'fruit_species_id': species.id, 'step_fruit_type': 'conventional', 'step_fruit_gross_kg': 32,
        })
        picking = scoped['stock.picking'].create(values)
        with self.assertRaises(UserError), self.cr.savepoint():
            picking.write({'fruit_fundo_id': False})
            picking._check_company(['partner_id'])
        move = scoped['stock.move'].create({
            'name': product.name, 'picking_id': picking.id, 'product_id': product.id,
            'product_uom': kg.id, 'product_uom_qty': 32, 'product_packaging_id': packaging.id,
            'location_id': picking.location_id.id, 'location_dest_id': picking.location_dest_id.id,
        })
        move.quantity = 32
        row = scoped['step.packing.picking.tag.line'].create({
            'picking_id': picking.id, 'tag_number': 'QA-T194-%s' % picking.id,
            'packaging_id': packaging.id, 'quantity': 4, 'kilos': 32,
        })
        picking.button_validate()
        self.assertEqual(picking.state, 'done')
        package = row.package_id
        self.assertEqual(package.step_tag_state, 'validated')
        self.assertEqual(package.fundo_id, farm)
        self.assertEqual(package.quant_ids.company_id, self.a)
        self.assertEqual(package.quant_ids.owner_id, producer)
        self.assertEqual(sum(package.quant_ids.mapped('quantity')), 32)
        self.assertFalse(move.stock_valuation_layer_ids)
