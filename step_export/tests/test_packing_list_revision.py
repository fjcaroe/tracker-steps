from lxml import etree
from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestPackingListRevision(TransactionCase):
    def _guide(self, shipment=None):
        partner = self.env['res.partner'].create({'name': 'QA T35 guide contact'})
        values = {'external_folio': 'QA-PACKING-35', 'partner_id': partner.id,
                  'origin_address': 'QA origin', 'destination_address': 'QA destination',
                  'carrier_id': partner.id, 'truck_plate': 'QA0035'}
        if shipment:
            values['step_export_shipment_id'] = shipment.id
        return self.env['step.dispatch.guide'].create(values)

    def test_guide_header_links_packing_list_and_assigns_saved_name(self):
        shipment = self.env['step.export.export'].create({'name': 'QA packing shipment'})
        guide = self._guide(shipment)
        self.assertIn(guide, shipment.dispatch_guide_ids)
        self.assertEqual(guide.step_export_shipment_id, shipment)
        packing = self.env['step.export.packing.list'].create({
            'name': False, 'shipment_id': shipment.id, 'guide_id': guide.id})
        self.assertTrue(packing.name.startswith('PL/'))
        self.assertEqual(packing.shipment_number, shipment.shipment_number)
        html, _ = self.env['ir.actions.report']._render_qweb_html(
            'step_export.action_report_export_packing_list', packing.ids)
        self.assertIn(packing.name.encode(), html)
        guide_tree = etree.fromstring(guide.get_view(view_type='form')['arch'].encode())
        self.assertTrue(guide_tree.xpath(".//sheet//field[@name='step_export_shipment_id']"))
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            guide.step_export_shipment_id = False

    def test_existing_membership_and_switch_keep_single_relation(self):
        guide = self._guide()
        first, second = self.env['step.export.export'].create([
            {'name': 'QA original shipment', 'dispatch_guide_ids': [(4, guide.id)]},
            {'name': 'QA new shipment'}])
        self.assertEqual(guide.step_export_shipment_id, first)
        guide.step_export_shipment_id = second
        self.assertNotIn(guide, first.dispatch_guide_ids)
        self.assertIn(guide, second.dispatch_guide_ids)
        self.assertEqual(guide.step_export_shipment_id, second)
        first.dispatch_guide_ids = guide
        self.assertFalse(guide.step_export_shipment_id)
        self.assertEqual(guide.step_export_shipment_ids, first | second)

    def test_unlinked_guide_still_rejected_and_shipment_selector_filters(self):
        shipment = self.env['step.export.export'].create({'name': 'QA unrelated shipment'})
        guide = self._guide()
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            self.env['step.export.packing.list'].create({'shipment_id': shipment.id, 'guide_id': guide.id})
        packing = self.env['step.export.packing.list'].new({'shipment_id': shipment.id, 'guide_id': guide.id})
        packing._onchange_shipment_guide()
        self.assertFalse(packing.guide_id)
        tree = etree.fromstring(packing.get_view(view_type='form')['arch'].encode())
        self.assertIn('available_guide_ids', tree.xpath(".//field[@name='guide_id']")[0].get('domain'))
