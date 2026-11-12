from lxml import etree
from odoo import Command
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import tagged
from odoo.tools.safe_eval import safe_eval
from odoo.addons.step_packing_dispatch.tests.test_dispatch import DispatchCase


@tagged('post_install', '-at_install')
class InterplantCase(DispatchCase):
    def interplant_fixture(self):
        self.fixture()
        self.branch = self.env['res.company'].create({'name': 'QA destination plant', 'parent_id': self.env.company.id})
        self.env.user.company_ids |= self.branch
        self.env = self.env(context=dict(self.env.context, allowed_company_ids=(self.env.company | self.branch).ids))
        self.destination = self.env['stock.warehouse'].search([('company_id', '=', self.branch.id)], limit=1)
        self.kind = self.env['step.freight.dispatch.type'].create({'name': 'QA interplant', 'step_recipient_kind': 'interplant'})
        self.driver = self.env['res.partner'].create({'name': 'QA driver', 'step_chofer': True})

    def transfer_guide(self, tags):
        guide = self.guide(dispatch_instruction_id=False, partner_id=self.branch.partner_id.id,
            dispatch_type_id=self.kind.id, step_destination_warehouse_id=self.destination.id,
            step_source_warehouse_id=self.location.warehouse_id.id, driver_partner_id=self.driver.id,
            transfer_reason_id=self.env['step.dispatch.transfer.reason'].search([], limit=1).id,
            load_tag_ids=[Command.set(tags.ids)])
        guide.action_load_pallet_detail()
        return guide

    def test_interplant_c_e_n_stock_pending_and_traceability(self):
        self.interplant_fixture()
        tags = self.tag('QA207-C', step_tag_kind='C') | self.tag('QA207-E') | self.tag('QA207-N', step_tag_kind='N')
        guide = self.transfer_guide(tags)
        guide.action_confirm()
        self.assertEqual(guide.picking_id.state, 'done')
        receipt = guide.step_destination_picking_id
        self.assertTrue(receipt)
        self.assertNotIn(receipt.state, ('done', 'cancel'))
        self.assertEqual(sum(receipt.move_line_ids.mapped('quantity_product_uom')), 30)
        self.assertFalse(receipt.step_interplant_tag_ids.quant_ids.filtered(lambda q: q.quantity > 0))
        self.assertEqual(set(receipt.step_interplant_tag_ids.mapped('name')), set(tags.mapped('name')))
        self.assertEqual(receipt.step_interplant_tag_ids.step_interplant_origin_tag_id, tags)
        self.assertAlmostEqual(sum(receipt.step_interplant_tag_ids.mapped('step_actual_kg')), 150)
        self.assertFalse(tags.quant_ids.filtered(lambda q: q.quantity > 0))
        self.assertEqual(set(tags.mapped('step_tag_state')), {'dispatched'})
        with self.assertRaises(UserError), self.cr.savepoint():
            receipt.step_interplant_tag_ids.action_step_validate_tag()
        receipt.with_company(self.branch).button_validate()
        self.assertEqual(receipt.state, 'done')
        self.assertEqual(set(receipt.step_interplant_tag_ids.mapped('step_tag_state')), {'validated'})
        self.assertEqual(sum(receipt.step_interplant_tag_ids.quant_ids.mapped('quantity')), 30)
        self.assertEqual(receipt.step_interplant_tag_ids.company_id, self.branch)
        old = receipt.move_line_ids.ids
        guide.action_confirm()
        self.assertEqual(guide.step_destination_picking_id, receipt)
        self.assertEqual(receipt.move_line_ids.ids, old)

    def test_reserved_and_duplicate_tags_rejected(self):
        self.interplant_fixture()
        tag = self.tag('QA207-RES')
        tag.quant_ids.reserved_quantity = 1
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self.transfer_guide(tag)
        tag.quant_ids.reserved_quantity = 0
        self.transfer_guide(tag)
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self.transfer_guide(tag)

    def test_destination_failure_rolls_back_source_stock(self):
        self.interplant_fixture()
        tag = self.tag('QA207-DUP')
        guide = self.transfer_guide(tag)
        self.env['stock.quant.package'].with_company(self.branch).create({'name': tag.name,
            'is_fruit_tag': True, 'step_tag_kind': 'C', 'company_id': self.branch.id})
        with self.assertRaises(UserError), self.cr.savepoint():
            guide.action_confirm()
        self.assertEqual(guide.state, 'draft')
        self.assertFalse(guide.picking_id)
        self.assertEqual(sum(tag.quant_ids.mapped('quantity')), 10)

    def test_pending_receipt_cannot_change_quantity_or_forge_origin(self):
        self.interplant_fixture()
        guide = self.transfer_guide(self.tag('QA207-IMM'))
        guide.action_confirm()
        receipt = guide.step_destination_picking_id
        with self.assertRaises(AccessError), self.cr.savepoint():
            receipt.step_interplant_guide_id = False
        with self.assertRaises(AccessError), self.cr.savepoint():
            receipt.step_interplant_tag_ids.step_process_reception_id = False
        receipt.move_line_ids.quantity = 9
        with self.assertRaises(UserError), self.cr.savepoint():
            receipt.with_company(self.branch).button_validate()
        self.assertFalse(receipt.step_interplant_tag_ids.quant_ids)

    def test_recipient_domains_and_native_views(self):
        self.interplant_fixture()
        guide = self.transfer_guide(self.tag('QA207-VIEW'))
        self.assertIn(self.branch.partner_id, self.env['res.partner'].search(guide.step_recipient_domain))
        self.assertNotIn(self.receiver, self.env['res.partner'].search(guide.step_recipient_domain))
        arch = etree.fromstring(guide.get_view(view_type='form')['arch'])
        names = [node.get('name') for node in arch.xpath('//sheet//field')]
        self.assertLess(names.index('dispatch_type_id'), names.index('partner_id'))
        self.assertIn('step_packing_interplant.tag_list', arch.xpath('//field[@name="load_tag_ids"]')[0].get('context'))
        for field in ('step_tag_kind', 'name', 'step_producer_id', 'box_count', 'step_actual_kg'):
            self.assertIn(field, self.env.ref('step_packing_interplant.tag_list').arch_db)
        self.assertEqual(self.env.ref('step_packing_interplant.receipts_menu').action.res_model, 'stock.picking')

    def test_lot_and_cross_branch_owner_are_preserved(self):
        self.interplant_fixture()
        self.producer.company_id = self.env.company
        self.product.tracking = 'lot'
        lot = self.env['stock.lot'].create({'name': 'QA207-LOT', 'product_id': self.product.id, 'company_id': self.env.company.id})
        tag = self.env['stock.quant.package'].create({'name': 'QA207-OWNED', 'is_fruit_tag': True,
            'step_tag_kind': 'C', 'step_producer_id': self.producer.id, 'box_count': 10,
            'step_packaging_id': self.packaging.id, 'especie_id': self.species.id,
            'step_tag_line_ids': [Command.create({'producer_id': self.producer.id,
                'product_id': self.product.id, 'lot_id': lot.id, 'quantity': 10, 'boxes': 10, 'kilos': 50})]})
        self.env['stock.quant']._update_available_quantity(self.product, self.location, 10,
            package_id=tag, lot_id=lot, owner_id=self.producer)
        tag.action_step_validate_tag()
        guide = self.transfer_guide(tag)
        guide.action_confirm()
        receipt = guide.step_destination_picking_id
        self.assertEqual(receipt.move_line_ids.owner_id, self.producer)
        self.assertEqual(receipt.move_line_ids.lot_id.name, lot.name)
        self.assertEqual(receipt.move_line_ids.lot_id.step_interplant_origin_lot_id, lot)
        self.assertEqual(receipt.move_line_ids.lot_id.company_id, self.branch)
        with self.assertRaises(AccessError), self.cr.savepoint():
            receipt.move_line_ids.lot_id.name = 'ALTERED'
        receipt.with_company(self.branch).button_validate()
        self.assertEqual(receipt.state, 'done')
        self.assertEqual(receipt.step_interplant_tag_ids.quant_ids.owner_id, self.producer)
        self.assertEqual(sum(receipt.step_interplant_tag_ids.quant_ids.mapped('quantity')), 10)
        self.assertFalse(receipt.move_ids.stock_valuation_layer_ids)

    def test_customer_and_producer_domains_and_unrelated_destination(self):
        self.interplant_fixture()
        guide = self.transfer_guide(self.tag('QA207-DOMAIN'))
        customer_type = self.env['step.freight.dispatch.type'].create({'name': 'QA customer', 'step_recipient_kind': 'customer'})
        producer_type = self.env['step.freight.dispatch.type'].create({'name': 'QA producer', 'step_recipient_kind': 'producer'})
        self.receiver.customer_rank = 1
        guide.write({'dispatch_type_id': customer_type.id, 'partner_id': self.receiver.id, 'step_destination_warehouse_id': False})
        self.assertIn(self.receiver, self.env['res.partner'].search(guide.step_recipient_domain))
        self.assertNotIn(self.producer, self.env['res.partner'].search(guide.step_recipient_domain))
        guide.write({'dispatch_type_id': producer_type.id, 'partner_id': self.producer.id})
        self.assertIn(self.producer, self.env['res.partner'].search(guide.step_recipient_domain))
        with self.assertRaises(ValidationError), self.cr.savepoint():
            guide.write({'dispatch_type_id': self.kind.id, 'partner_id': self.receiver.id})

    def test_destination_operator_can_receive_without_source_membership(self):
        self.interplant_fixture()
        farm = self.env['step.fundo'].create({'name': 'QA origin farm', 'partner_id': self.producer.id,
            'company_id': self.env.company.id})
        guide = self.transfer_guide(self.tag('QA207-RECEIVER', fundo_id=farm.id))
        guide.action_confirm()
        receipt = guide.step_destination_picking_id
        user = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'QA destination receiver', 'login': 'qa207-destination',
            'company_id': self.branch.id, 'company_ids': [Command.set(self.branch.ids)],
            'groups_id': [Command.set([self.env.ref('base.group_user').id, self.env.ref('stock.group_stock_user').id])]})
        scoped = receipt.with_user(user).with_context(allowed_company_ids=self.branch.ids)
        scoped.button_validate()
        self.assertEqual(receipt.state, 'done')
        self.assertEqual(user.company_ids, self.branch)
        self.assertNotIn(self.branch, farm.company_ids)
        self.assertEqual(receipt.step_interplant_tag_ids.fundo_id, farm)

    def test_dispatch_detail_must_equal_stock_and_generic_stock_can_transfer(self):
        self.interplant_fixture()
        tag = self.tag('QA207-DETAIL')
        guide = self.transfer_guide(tag)
        guide.line_ids.quantity = 9
        with self.assertRaises(UserError), self.cr.savepoint():
            guide.action_confirm()
        self.assertEqual(sum(tag.quant_ids.mapped('quantity')), 10)
        guide.action_cancel()
        plain = self.env['product.product'].create({'name': 'QA207 material', 'is_storable': True})
        self.env['stock.quant']._update_available_quantity(plain, self.location, 6)
        generic = self.guide(dispatch_instruction_id=False, partner_id=self.branch.partner_id.id,
            dispatch_type_id=self.kind.id, step_destination_warehouse_id=self.destination.id,
            step_source_warehouse_id=self.location.warehouse_id.id, driver_partner_id=self.driver.id,
            transfer_reason_id=self.env['step.dispatch.transfer.reason'].search([], limit=1).id,
            line_ids=[Command.create({'product_id': plain.id, 'description': plain.name,
                'product_uom_id': plain.uom_id.id, 'quantity': 6})])
        generic.action_confirm()
        receipt = generic.step_destination_picking_id
        self.assertNotEqual(receipt.state, 'done')
        receipt.with_company(self.branch).button_validate()
        self.assertEqual(receipt.state, 'done')
        self.assertEqual(self.env['stock.quant']._get_available_quantity(plain, self.destination.lot_stock_id), 6)


    def source_only_operator(self, guide):
        source = guide.company_id
        user = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'QA source dispatcher', 'login': 'qa209-source',
            'company_id': source.id, 'company_ids': [Command.set((source | self.branch).ids)],
            'groups_id': [Command.set([self.env.ref('base.group_user').id,
                                      self.env.ref('stock.group_stock_manager').id])]})
        return guide.with_user(user).with_context(allowed_company_ids=source.ids)

    def test_single_active_source_finds_destination_and_confirms_without_selector(self):
        self.interplant_fixture()
        guide = self.transfer_guide(self.tag('QA209-ONE'))
        guide.step_destination_warehouse_id = False
        scoped = self.source_only_operator(guide)
        source = scoped.env.company
        memberships = scoped.env.user.company_ids
        self.assertFalse(scoped.env['stock.warehouse'].search([('company_id','=',self.branch.id)]))
        self.assertEqual(scoped._destination_warehouses(), self.destination)
        scoped._onchange_interplant_destination()
        self.assertEqual(scoped.step_destination_warehouse_id, self.destination)
        # Existing drafts or imports may not trigger an onchange: confirmation must resolve it too.
        scoped.step_destination_warehouse_id = False
        scoped.action_confirm()
        receipt = scoped.with_company(self.branch).step_destination_picking_id
        self.assertEqual(receipt.picking_type_id, self.destination.in_type_id)
        self.assertNotIn(receipt.state, ('done','cancel'))
        self.assertFalse(receipt.step_interplant_tag_ids.quant_ids.filtered(lambda q: q.quantity > 0))
        self.assertEqual(scoped.env.company, source)
        self.assertEqual(scoped.env.companies, source)
        self.assertEqual(scoped.env.user.company_ids, memberships)

    def test_multiple_destination_warehouses_use_native_selector_scope(self):
        self.interplant_fixture()
        second = self.env['stock.warehouse'].create({'name':'QA second destination','code':'Q209','company_id':self.branch.id})
        guide = self.transfer_guide(self.tag('QA209-MULTI'))
        guide.step_destination_warehouse_id = False
        scoped = self.source_only_operator(guide)
        scoped._onchange_interplant_destination()
        self.assertFalse(scoped.step_destination_warehouse_id)
        arch = etree.fromstring(scoped.get_view(view_type='form')['arch'])
        field = arch.xpath('//field[@name="step_destination_warehouse_id"]')[0]
        context = safe_eval(field.get('context'), {'step_destination_company_id':self.branch.id})
        choices = scoped.env['stock.warehouse'].with_context(**context).name_search(args=[('company_id','=',self.branch.id)])
        self.assertEqual({row[0] for row in choices}, {self.destination.id,second.id})
        scoped.step_destination_warehouse_id = second
        scoped.action_confirm()
        receipt = scoped.with_company(self.branch).step_destination_picking_id
        self.assertEqual(receipt.location_dest_id,second.lot_stock_id)
        self.assertNotEqual(receipt.state,'done')

    def test_destination_lookup_does_not_grant_unassigned_branch(self):
        self.interplant_fixture()
        guide = self.transfer_guide(self.tag('QA209-DENIED'))
        scoped = self.source_only_operator(guide)
        scoped.env.user.sudo().company_ids = [Command.set(guide.company_id.ids)]
        scoped.invalidate_recordset()
        self.assertFalse(scoped.step_destination_company_id)
        self.assertFalse(scoped._destination_warehouses())
        with self.assertRaises(ValidationError), self.cr.savepoint():
            scoped._check_recipient()


    def test_existing_native_destination_lot_and_return_keep_both_move_origins(self):
        self.interplant_fixture()
        source = self.env.company
        self.product.tracking = 'lot'
        original_lot = self.env['stock.lot'].create({'name':'QA209-EXISTING',
            'product_id':self.product.id,'company_id':source.id})
        existing_lot = self.env['stock.lot'].with_company(self.branch).create({'name':original_lot.name,
            'product_id':self.product.id,'company_id':self.branch.id})
        tag = self.env['stock.quant.package'].create({'name':'QA209-REUSE','is_fruit_tag':True,
            'step_tag_kind':'C','step_producer_id':self.producer.id,'box_count':10,
            'step_packaging_id':self.packaging.id,'especie_id':self.species.id,
            'step_tag_line_ids':[Command.create({'producer_id':self.producer.id,
                'product_id':self.product.id,'lot_id':original_lot.id,'quantity':10,'boxes':10,'kilos':50})]})
        self.env['stock.quant']._update_available_quantity(self.product,self.location,10,package_id=tag,lot_id=original_lot)
        tag.action_step_validate_tag()
        guide = self.source_only_operator(self.transfer_guide(tag))
        guide.action_confirm()
        receipt = guide.with_company(self.branch).step_destination_picking_id
        self.assertEqual(receipt.move_line_ids.lot_id,existing_lot)
        self.assertFalse(existing_lot.step_interplant_origin_lot_id)
        self.assertEqual(receipt.move_line_ids.step_interplant_origin_line_id.lot_id,original_lot)
        wrong = self.env['stock.lot'].with_company(self.branch).create({'name':'QA209-WRONG',
            'product_id':self.product.id,'company_id':self.branch.id})
        receipt.move_line_ids.lot_id = wrong
        with self.assertRaises(UserError), self.cr.savepoint():
            receipt.button_validate()
        receipt.move_line_ids.lot_id = existing_lot
        receipt.button_validate()
        self.assertEqual(receipt.state,'done')
        received = receipt.step_interplant_tag_ids
        self.kind.company_ids |= self.branch
        returned = guide.with_company(self.branch).copy({'external_folio':'QA209-RETURN','state':'draft',
            'company_id':self.branch.id,'partner_id':source.partner_id.id,
            'step_source_warehouse_id':self.destination.id,
            'step_destination_warehouse_id':self.location.warehouse_id.id,
            'picking_id':False,'step_destination_picking_id':False,
            'load_tag_ids':[Command.set(received.ids)],'line_ids':[Command.clear()]})
        returned.action_load_pallet_detail()
        returned.action_confirm()
        arrival = returned.with_company(source).step_destination_picking_id
        self.assertEqual(arrival.move_line_ids.lot_id,original_lot)
        self.assertFalse(original_lot.step_interplant_origin_lot_id)
        self.assertNotEqual(arrival.state,'done')
        self.assertFalse(arrival.step_interplant_tag_ids.quant_ids.filtered(lambda q:q.quantity > 0))
        arrival.button_validate()
        self.assertEqual(arrival.state,'done')
        self.assertEqual(arrival.move_line_ids.step_interplant_origin_line_id.lot_id,existing_lot)
        self.assertEqual(sum(arrival.step_interplant_tag_ids.quant_ids.mapped('quantity')),10)
        self.assertEqual(arrival.step_interplant_tag_ids.step_interplant_origin_tag_id,received)


    def test_legacy_tag_company_survives_migration_and_departure(self):
        from odoo.addons.step_packing_interplant.hooks import preserve_legacy_tag_companies
        self.interplant_fixture()
        tag = self.tag('QA209-LEGACY', step_tag_kind='C')
        source = tag.company_id
        self.env.flush_all()
        self.cr.execute('UPDATE stock_quant_package SET step_packing_company_id=NULL WHERE id=%s', [tag.id])
        tag.invalidate_recordset(['step_packing_company_id'])
        self.assertFalse(tag.step_packing_company_id)
        self.assertEqual(tag.company_id, source)
        audit = (tag.write_uid, tag.write_date)
        preserve_legacy_tag_companies(self.env)
        preserve_legacy_tag_companies(self.env)  # Safe on an already migrated database.
        self.assertEqual((tag.write_uid, tag.write_date), audit)
        self.assertEqual(tag.step_packing_company_id, source)
        guide = self.source_only_operator(self.transfer_guide(tag))
        guide.action_confirm()
        self.assertFalse(tag.quant_ids.filtered(lambda q: q.quantity > 0))
        self.assertEqual(tag.company_id, source)
        receipt = guide.with_company(self.branch).step_destination_picking_id
        self.assertNotIn(receipt.state, ('done', 'cancel'))
        receipt.button_validate()
        self.assertEqual(receipt.state, 'done')
        self.assertEqual(receipt.step_interplant_tag_ids.step_interplant_origin_tag_id, tag)
        self.assertEqual(sum(receipt.step_interplant_tag_ids.quant_ids.mapped('quantity')), 10)
