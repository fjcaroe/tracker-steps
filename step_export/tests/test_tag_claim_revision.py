from lxml import etree
from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestTagClaimRevision(TransactionCase):
    def _fixtures(self):
        receiver = self.env['res.partner'].create({'name': 'QA T35 claim receiver'})
        tags = self.env['stock.quant.package'].with_context(default_step_tag_kind='E').create([
            {'name': 'QA T35 selected A', 'is_fruit_tag': True, 'box_count': 184},
            {'name': 'QA T35 selected B', 'is_fruit_tag': True, 'box_count': 184},
            {'name': 'QA T35 unrelated', 'is_fruit_tag': True}])
        shipment = self.env['step.export.export'].create({'name': 'QA T35 tags', 'tag_ids': [(6, 0, tags[:2].ids)]})
        claim = self.env['step.export.customer.claim'].create({'name': 'QA T35 per-tag claim',
            'receiver_id': receiver.id, 'shipment_ids': [(4, shipment.id)]})
        return tags, shipment, claim

    def test_assignment_is_the_existing_bidirectional_relation(self):
        tags, shipment, _ = self._fixtures()
        self.assertIn(shipment, tags[0].step_export_shipment_ids)
        self.assertEqual(tags[0].step_export_shipment_numbers, shipment.shipment_number)
        shipment.tag_ids = tags[1]
        self.assertFalse(tags[0].step_export_shipment_ids)
        self.assertFalse(tags[0].step_export_shipment_numbers)
        action = self.env.ref('step_export.action_export_consult_tags')
        tree = etree.fromstring(tags.get_view(view_id=action.view_id.id, view_type='list')['arch'].encode())
        names = tree.xpath('.//field/@name')
        for name in ('name', 'step_export_shipment_ids', 'fundo_id', 'especie_id', 'variedad_id', 'box_count', 'kilos_total'):
            self.assertIn(name, names)
        if 'step_tag_state' in tags._fields:
            self.assertIn('step_tag_state', names)
        reserve = self.env.ref('step_export.menu_step_export_stock_reservation')
        consult = self.env.ref('step_export.menu_step_export_consult_tags')
        self.assertEqual(consult.parent_id, reserve.parent_id)
        self.assertGreater(consult.sequence, reserve.sequence)

    def test_unrelated_tags_rejected_on_save_not_only_acceptance(self):
        tags, shipment, claim = self._fixtures()
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            claim.tag_ids = tags[2]
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            self.env['step.export.claim.line'].create({'claim_id': claim.id, 'tag_id': tags[2].id, 'claimed_amount_usd': 10})
        self.assertEqual(claim.available_tag_ids, tags[:2])

    def test_per_tag_amounts_total_acceptance_and_immutability(self):
        tags, shipment, claim = self._fixtures()
        claim.action_load_shipment_tags()
        self.assertEqual(claim.line_ids.mapped('tag_id'), tags[:2])
        first = claim.line_ids.filtered(lambda line: line.tag_id == tags[0])
        second = claim.line_ids - first
        first.write({'claimed_amount_usd': 1000, 'accepted_amount_usd': 500})
        second.write({'claimed_amount_usd': 1000, 'accepted_amount_usd': 600})
        self.assertEqual(claim.claimed_amount_usd, 2000)
        self.assertEqual(claim.accepted_amount_usd, 1100)
        self.assertEqual(claim.tag_ids, tags[:2])
        claim.action_accept()
        self.assertIn(claim, shipment.claim_ids)
        self.assertIn(claim, tags[0].step_export_claim_ids)
        for operation in (lambda: first.write({'accepted_amount_usd': 0}), lambda: first.unlink(),
                          lambda: self.env['step.export.claim.line'].create({'claim_id': claim.id, 'tag_id': tags[2].id})):
            with self.assertRaises(UserError), self.env.cr.savepoint():
                operation()

    def test_amount_bounds_and_deletion_recalculate(self):
        tags, _, claim = self._fixtures()
        line = self.env['step.export.claim.line'].create({'claim_id': claim.id, 'tag_id': tags[0].id,
            'claimed_amount_usd': 100, 'accepted_amount_usd': 50})
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            line.accepted_amount_usd = 101
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            line.claimed_amount_usd = -1
        line.unlink()
        self.assertEqual(claim.claimed_amount_usd, 0)
        self.assertFalse(claim.tag_ids)

    def test_legacy_totals_survive_without_detailed_lines(self):
        tags, _, claim = self._fixtures()
        claim.write({'claimed_amount_usd': 2000, 'accepted_amount_usd': 1100, 'tag_ids': [(4, tags[0].id)]})
        claim.action_accept()
        self.assertEqual(claim.claimed_amount_usd, 2000)
        self.assertEqual(claim.accepted_amount_usd, 1100)

    def test_settlement_uses_tag_amounts_for_each_shipment(self):
        tags, first, claim = self._fixtures()
        first.tag_ids = tags[0]
        second = self.env['step.export.export'].create({'name': 'QA T35 second shipment', 'tag_ids': [(4, tags[1].id)]})
        claim.shipment_ids = first | second
        claim.action_load_shipment_tags()
        for line in claim.line_ids:
            line.write({'claimed_amount_usd': 1000, 'accepted_amount_usd': 500 if line.tag_id == tags[0] else 600})
        claim.action_accept()
        first_line = self.env['step.export.receiver.settlement.line'].new({'shipment_id': first.id})
        second_line = self.env['step.export.receiver.settlement.line'].new({'shipment_id': second.id})
        first_line._compute_claim()
        second_line._compute_claim()
        self.assertEqual(first_line.claim_usd, 500)
        self.assertEqual(second_line.claim_usd, 600)
