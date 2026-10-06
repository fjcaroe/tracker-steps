from lxml import etree

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "step_producers")
class TestProducerApp(TransactionCase):
    def test_accounting_settings_open_active_company_without_creating_records(self):
        menu = self.env.ref('step_producers.menu_producer_accounting')
        count = self.env['res.company'].search_count([])
        action = menu.action.run()
        self.assertEqual(action['res_id'], self.env.company.id)
        self.assertEqual(action['views'], [(self.env.ref('step_producers.view_producer_accounting_form').id, 'form')])
        self.assertEqual(self.env['res.company'].search_count([]), count)
        other = self.env['res.company'].create({'name': 'Empresa ajustes activos QA'})
        self.assertEqual(menu.with_company(other).action.run()['res_id'], other.id)
        self.assertGreater(self.env.ref('step_producers.view_producer_accounting_form').priority,
                           self.env.ref('base.view_company_form').priority)
        self.assertEqual(self.env.ref('step_producers.action_producer_accounting').views[0][1], 'list')

    def test_producer_uses_existing_farms_rates_and_estimates(self):
        producer = self.env["res.partner"].create({
            "name": "Productor prueba Productores", "is_productor": True,
        })
        fundo = self.env["step.fundo"].create({
            "name": "Fundo prueba Productores", "partner_id": producer.id,
            "company_id": self.env.company.id,
        })
        rate = self.env["step.export.grower.rate"].create({
            "name": "Tarifa prueba Productores", "producer_id": producer.id,
            "company_id": self.env.company.id,
        })
        self.assertEqual(producer.step_producer_fundo_count, 1)
        self.assertEqual(producer.step_producer_rate_count, 1)
        self.assertEqual(producer.action_step_producer_fundos()["domain"],
                         [("partner_id", "=", producer.id)])
        self.assertEqual(producer.action_step_producer_rates()["domain"],
                         [("producer_id", "=", producer.id)])
        self.assertEqual(fundo.partner_id, producer)
        self.assertEqual(rate.producer_id, producer)

    def test_app_reuses_packing_and_export_actions(self):
        root = self.env.ref("step_producers.menu_step_producers_root")
        self.assertEqual(root.action, self.env.ref("step_producers.action_step_producers_dashboard"))
        pairs = {
            "step_producers.menu_step_producers_estimates": "step_producers.action_step_export_estimate",
            "step_producers.menu_step_producers_rates": "step_producers.action_step_export_grower_rate",
            "step_producers.menu_step_producers_settlements": "step_producers.action_export_producer_settlement",
        }
        if self.env.registry.get('step.export.sales.program'):
            pairs.update({
                "step_export.menu_step_export_packing_line": "step_packing.action_step_packing_line",
                "step_export.menu_step_export_packing_tag_type": "step_packing.action_step_packing_tag_type",
            })
        for menu_xmlid, action_xmlid in pairs.items():
            self.assertEqual(self.env.ref(menu_xmlid).action,
                             self.env.ref(action_xmlid), menu_xmlid)

    def test_partner_fields_are_in_their_business_tabs(self):
        arch = self.env["res.partner"].get_view(
            view_id=self.env.ref("base.view_partner_form").id, view_type="form")["arch"]
        tree = etree.fromstring(arch.encode())
        self.assertTrue(tree.xpath("//page[@name='productor']//field[@name='productor_name']"))
        self.assertFalse(tree.xpath("//page[@name='agri']//field[@name='productor_name']"))
        if self.env.registry.get('step.export.sales.program'):
            self.assertTrue(tree.xpath("//page[@name='step_export_partner']//field[@name='step_export']"))

    def test_menu_follows_client_process_groups(self):
        root = self.env.ref("step_producers.menu_step_producers_root")
        children = self.env["ir.ui.menu"].search([("parent_id", "=", root.id)], order="sequence,id")
        self.assertEqual(children.with_context(lang="es_CL").mapped("name"), [
            "Inicio", "Planificación", "Control Contratos", "Control fruta", "Liquidación", "Maestros", "Configuraciones"])
        self.assertEqual(self.env.ref("step_producers.menu_step_producers_contracts").parent_id,
                         self.env.ref("step_producers.menu_step_producers_planning_group"))
        self.assertEqual(self.env.ref("step_producers.menu_step_producers_fundos").parent_id,
                         self.env.ref("step_producers.menu_step_producers_config_group"))
