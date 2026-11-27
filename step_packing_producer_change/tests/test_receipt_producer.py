from lxml import etree

from odoo import Command
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import tagged
from odoo.addons.step_packing_reception_revision.tests.test_simple_reception import SimpleReceptionCase


@tagged('post_install', '-at_install', 'step_packing_producer_change')
class ReceiptProducerCase(SimpleReceptionCase):
    def prepare(self):
        self.received = self.receipt((160, 240))
        self.received.button_validate()
        self.tags = self.received.fruit_tag_line_ids.package_id
        self.other = self.env['res.partner'].create({'name': 'QA246 productor corregido', 'is_productor': True})

    def wizard(self, picking=None, producer=None):
        receipt = picking or self.received
        return self.env['step.receipt.producer.change'].create({
            'picking_id': receipt.id, 'previous_producer_id': receipt.partner_id.id,
            'producer_id': (producer or self.other).id, 'reason': 'Corrección de productor recibido QA246'})

    def snapshot(self):
        return [(tag.id, tag.name, tag.fundo_id.id, tag.especie_id.id, tag.variedad_id.id,
                 tag.step_tag_state, tag.box_count, tag.step_actual_kg,
                 [(q.product_id.id, q.lot_id.id, q.location_id.id, q.quantity, q.reserved_quantity, q.in_date)
                  for q in tag.quant_ids]) for tag in self.tags]

    def test_received_producer_stock_history_and_repeat(self):
        self.prepare()
        before = self.snapshot()
        original = self.received.move_line_ids
        history = original.read(['owner_id', 'quantity', 'lot_id', 'result_package_id', 'location_dest_id'])
        self.wizard().action_apply()
        self.assertEqual(self.received.partner_id, self.other)
        self.assertEqual(self.tags.step_producer_id, self.other)
        self.assertEqual(self.tags.step_tag_line_ids.producer_id, self.other)
        self.assertEqual(self.tags.quant_ids.owner_id, self.other)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(original.read(['owner_id', 'quantity', 'lot_id', 'result_package_id', 'location_dest_id']), history)
        self.assertEqual(len(self.received.step_producer_change_move_ids), 4)
        self.assertFalse(self.received.step_producer_change_move_ids.stock_valuation_layer_ids)
        self.wizard(producer=self.producer).action_apply()
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.tags.owner_id, self.producer)
        self.assertEqual(len(self.received.step_producer_change_move_ids), 8)

    def test_reservations_remain_on_same_stock(self):
        self.prepare()
        tag = self.tags[0]
        quant = tag.quant_ids
        move = self.env['stock.move'].create({
            'name': 'QA246 reserva', 'product_id': self.product.id,
            'product_uom': self.product.uom_id.id, 'product_uom_qty': 80,
            'location_id': quant.location_id.id, 'location_dest_id': quant.location_id.id})
        move._action_confirm(merge=False)
        move._do_unreserve()
        move._update_reserved_quantity(80, quant.location_id, package_id=tag, owner_id=self.producer, strict=True)
        line = move.move_line_ids
        before = self.snapshot()
        self.wizard().action_apply()
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(line.owner_id, self.other)
        self.assertEqual(line.quantity, 80)
        self.assertEqual(line.package_id, tag)
        self.assertEqual(tag.quant_ids.reserved_quantity, 80)

    def test_internal_transfer_is_still_inventory(self):
        self.prepare()
        tag = self.tags[0]
        location = self.env['stock.location'].create({'name': 'QA246 cámara', 'usage': 'internal',
            'location_id': self.wh.view_location_id.id, 'company_id': self.env.company.id})
        move = self.env['stock.move'].create({
            'name': 'QA246 traslado', 'product_id': self.product.id, 'product_uom': self.product.uom_id.id,
            'state': 'confirmed', 'picked': True,
            'product_uom_qty': 160, 'location_id': self.wh.lot_stock_id.id, 'location_dest_id': location.id,
            'move_line_ids': [Command.create({'product_id': self.product.id, 'product_uom_id': self.product.uom_id.id,
                'quantity': 160, 'location_id': self.wh.lot_stock_id.id, 'location_dest_id': location.id,
                'package_id': tag.id, 'result_package_id': tag.id, 'owner_id': self.producer.id})]})
        move._action_done()
        self.assertEqual(tag.quant_ids.location_id, location)
        self.wizard().action_apply()
        self.assertEqual(tag.location_id, location)
        self.assertEqual(tag.owner_id, self.other)

    def test_processed_dispatched_partial_and_missing_stock_rejected(self):
        self.prepare()
        for state in ('processed', 'dispatched', 'repalletized', 'void'):
            with self.cr.savepoint():
                self.tags[0].step_tag_state = state
                with self.assertRaises(UserError), self.cr.savepoint():
                    self.wizard().action_apply()
                self.tags[0].step_tag_state = 'validated'
        self.env['stock.quant']._update_available_quantity(self.product, self.wh.lot_stock_id,
            -1, package_id=self.tags[0], owner_id=self.producer)
        with self.assertRaises(UserError), self.cr.savepoint():
            self.wizard().action_apply()
        self.assertEqual(self.received.partner_id, self.producer)

    def test_stale_and_direct_changes_rejected(self):
        self.prepare()
        stale = self.wizard()
        self.wizard().action_apply()
        with self.assertRaises(UserError), self.cr.savepoint():
            stale.action_apply()
        for record, values in ((self.received, {'partner_id': self.producer.id}),
                               (self.tags, {'step_producer_id': self.producer.id}),
                               (self.tags.step_tag_line_ids, {'producer_id': self.producer.id}),
                               (self.received.step_producer_change_move_ids, {'step_producer_change_reason': 'fake'})):
            with self.assertRaises(UserError), self.cr.savepoint():
                record.with_context(_step_receipt_producer=True).write(values)

    def test_foreign_producer_and_read_only_user_rejected(self):
        self.prepare()
        foreign_company = self.env['res.company'].create({'name': 'QA246 ajena'})
        foreign = self.env['res.partner'].create({'name': 'QA246 ajeno', 'is_productor': True, 'company_id': foreign_company.id})
        with self.assertRaises(UserError), self.cr.savepoint():
            self.wizard(producer=foreign).action_apply()
        from odoo.tests.common import new_test_user
        reader = new_test_user(self.env, login='qa246.reader', groups='base.group_user,stock.group_stock_user')
        with self.assertRaises(AccessError), self.cr.savepoint():
            self.received.with_user(reader).action_step_change_received_producer()

    def test_inventory_manager_can_apply_without_sudo(self):
        self.prepare()
        from odoo.tests.common import new_test_user
        manager = new_test_user(self.env(context=dict(self.env.context, no_reset_password=True)),
            login='qa246.manager', groups='stock.group_stock_manager',
            company_id=self.env.company.id, company_ids=[Command.set(self.env.company.ids)])
        action = self.tags[0].with_user(manager).action_step_change_received_producer()
        wizard = self.env[action['res_model']].with_user(manager).with_context(action['context']).create({
            'producer_id': self.other.id, 'reason': 'Corrección operativa QA246'})
        self.assertFalse(wizard.env.su)
        wizard.action_apply()
        self.assertEqual(self.tags.owner_id, self.other)
        self.assertEqual(self.received.step_producer_change_move_ids.create_uid, manager)

    def test_forms_both_entry_points(self):
        self.prepare()
        for model, ref in (
                ('stock.picking', 'step_packing_reception_revision.view_process_reception_form'),
                ('stock.quant.package', 'step_inventory_packing.view_quant_package_form_steps_fruit')):
            view = self.env[model].get_view(self.env.ref(ref).id, 'form')
            tree = etree.fromstring(view['arch'])
            self.assertTrue(tree.xpath('//button[@name="action_step_change_received_producer"]'))
        action = self.tags[0].action_step_change_received_producer()
        self.assertEqual(action['context']['default_picking_id'], self.received.id)
