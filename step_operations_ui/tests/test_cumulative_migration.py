from odoo.tests import TransactionCase, tagged
from odoo.addons.step_operations_ui.migration_helpers import mark_freight_carriers


@tagged('post_install','-at_install')
class TestCumulativeMigration(TransactionCase):
    def test_native_only_sources_keep_ids_and_mark_only_used_contacts(self):
        used,unrelated=self.env['res.partner'].create([
            {'name':'QA native freight carrier','is_freight_carrier':False},
            {'name':'QA unrelated contact','is_freight_carrier':False}])
        self.env.cr.execute('CREATE TEMP TABLE step_freight_tariff (freight_carrier_id INTEGER)')
        self.env.cr.execute('INSERT INTO step_freight_tariff VALUES (%s)',(used.id,))
        mark_freight_carriers(self.env.cr)
        self.env.invalidate_all()
        self.assertTrue(used.is_freight_carrier)
        self.assertFalse(unrelated.is_freight_carrier)
        self.assertEqual(mark_freight_carriers(self.env.cr),0)

    def test_legacy_sources_are_supported_before_the_rename(self):
        contact=self.env['res.partner'].create({'name':'QA legacy freight carrier','is_freight_carrier':False})
        self.env.cr.execute('CREATE TEMP TABLE x_tarifa_de_fletes (x_studio_transportista INTEGER)')
        self.env.cr.execute('INSERT INTO x_tarifa_de_fletes VALUES (%s)',(contact.id,))
        mark_freight_carriers(self.env.cr)
        self.env.invalidate_all()
        self.assertTrue(contact.is_freight_carrier)
