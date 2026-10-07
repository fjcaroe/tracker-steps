import importlib.util
from pathlib import Path
from lxml import etree
from odoo.tests import TransactionCase, tagged
from odoo.tools.safe_eval import safe_eval


@tagged('post_install', '-at_install')
class TestShipmentRevision(TransactionCase):

    def test_participant_selectors_use_existing_export_contact_flag(self):
        eligible = self.env['res.partner'].create({'name': 'QA export participant', 'step_export': True})
        regular = self.env['res.partner'].create({'name': 'QA regular contact', 'step_export': False})
        tree = etree.fromstring(self.env['step.export.export'].get_view(view_type='form')['arch'].encode())
        for field in ('carrier_id', 'consignee_id', 'notify_id', 'freight_forwarder_id', 'customs_agent_id'):
            node = tree.xpath(".//field[@name='%s']" % field)[0]
            choices = self.env['res.partner'].search(safe_eval(node.get('domain')))
            self.assertIn(eligible, choices)
            self.assertNotIn(regular, choices)

    def test_ports_use_native_customs_master_and_keep_historical_text(self):
        origin = self.env['l10n_cl.customs_port'].create({'name': 'QA native origin port', 'code': 999999991, 'country_id': self.env.ref('base.cl').id})
        destination = self.env['l10n_cl.customs_port'].create({'name': 'QA native destination port', 'code': 999999992, 'country_id': self.env.ref('base.us').id})
        shipment = self.env['step.export.export'].create({'name': 'QA port selection',
            'origin_port': 'Historical origin retained', 'origin_port_id': origin.id, 'destination_port_id': destination.id})
        self.assertEqual(shipment.origin_port_id._name, 'l10n_cl.customs_port')
        self.assertEqual(shipment.destination_port_id, destination)
        self.assertEqual(shipment.origin_port, 'Historical origin retained')
        tree = etree.fromstring(shipment.get_view(view_type='form')['arch'].encode())
        self.assertTrue(tree.xpath(".//field[@name='origin_port_id']"))
        self.assertTrue(tree.xpath(".//field[@name='destination_port_id']"))

    def test_port_migration_avoids_ambiguous_names_and_preserves_records(self):
        ports = self.env['l10n_cl.customs_port'].create([
            {'name': 'QA unique customs port', 'code': 999999993, 'country_id': self.env.ref('base.cl').id},
            {'name': 'QA ambiguous customs port', 'code': 999999994, 'country_id': self.env.ref('base.cl').id},
            {'name': 'QA ambiguous customs port', 'code': 999999995, 'country_id': self.env.ref('base.us').id}])
        unique = self.env['step.export.export'].create({'name': 'QA migration unique', 'origin_port': ' qa UNIQUE customs port ', 'destination_port': '999999993'})
        ambiguous = self.env['step.export.export'].create({'name': 'QA migration ambiguous', 'origin_port': 'QA ambiguous customs port'})
        ids = (unique | ambiguous).ids
        path = Path(__file__).resolve().parents[1] / 'migrations/18.0.2.9.6/post-migrate.py'
        spec = importlib.util.spec_from_file_location('export_port_migration', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.migrate(self.env.cr, '18.0.2.9.5')
        self.assertEqual(unique.origin_port_id, ports[0])
        self.assertEqual(unique.destination_port_id, ports[0])
        self.assertFalse(ambiguous.origin_port_id)
        self.assertEqual(unique.origin_port, ' qa UNIQUE customs port ')
        self.assertEqual((unique | ambiguous).ids, ids)
