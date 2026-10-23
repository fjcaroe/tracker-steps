from datetime import date
from lxml import etree
from odoo import Command
from odoo.tests import Form
from odoo.tests.common import TransactionCase
from odoo.tools.safe_eval import safe_eval


class CatalogCurrencyCase(TransactionCase):
    def test_existing_country_market_relation_and_native_menu(self):
        country = self.env.ref('base.cl')
        countries = self.env['res.country'].search_count([])
        market = self.env['step.fruit.market'].create({'code': 'QT110', 'name': 'QA mercado', 'abbreviation': 'QA'})
        with Form(country, view='base.view_country_form') as form:
            form.fruit_market_id = market
        self.assertEqual(country.fruit_market_id, market)
        self.assertEqual(self.env['res.country'].search_count([]), countries)
        self.assertEqual(country._fields['fruit_market_id'].comodel_name, 'step.fruit.market')
        menu = self.env.ref('step_export_catalog_currency.countries_menu')
        self.assertEqual(menu.action, self.env.ref('base.action_country'))
        self.assertEqual(menu.parent_id, self.env.ref('step_export.menu_step_export_config_export'))

    def test_native_port_create_country_and_existing_shipment_relation(self):
        action = self.env.ref('step_export_catalog_currency.ports_action')
        self.assertEqual(action.res_model, 'l10n_cl.customs_port')
        self.assertEqual([mode for _, mode in action.views], ['list', 'form'])
        self.assertEqual(action.views[0][0], self.env.ref('l10n_cl_edi_exports.customs_port_tree_view').id)
        with Form(self.env[action.res_model], view='step_export_catalog_currency.port_form') as form:
            form.name = 'QA puerto T110'
            form.code = 900110
            form.country_id = self.env.ref('base.cl')
        port = self.env[action.res_model].search([('name', '=', 'QA puerto T110')])
        self.assertEqual(len(port), 1)
        self.assertEqual(port.country_id, self.env.ref('base.cl'))
        self.assertEqual(self.env['step.export.export']._fields['origin_port_id'].comodel_name, port._name)
        self.assertEqual(self.env['step.export.export']._fields['destination_port_id'].comodel_name, port._name)

    def program(self, currency, rate):
        season = self.env['step.temporada'].create({'name': 'QA T111 temporada'})
        species = self.env['step.especie'].create({'name': 'QA T111 fruta', 'type_especie': 'frutal', 'group_especie': 'seco'})
        receiver = self.env['res.partner'].create({'name': 'QA T111 recibidor'})
        product = self.env['product.product'].create({'name': 'QA T111 producto', 'grupo_labor': 'pack'})
        pallet = self.env['stock.package.type'].create({'name': 'QA T111 pallet'})
        return self.env['step.export.sales.program'].create({
            'name': 'QA T111 programa', 'season_id': season.id, 'species_id': species.id,
            'partner_id': receiver.id, 'product_id': product.id, 'package_type_id': pallet.id,
            'date_start': date(2026, 11, 2), 'date_end': date(2026, 11, 8),
            'currency_id': currency.id, 'rate_to_usd': rate, 'pallets_per_container': 1,
            'boxes_per_pallet': 10, 'kg_per_box': 10,
            'line_ids': [Command.create({'week_start': date(2026, 11, 2), 'container_qty': 1, 'price_per_kg': 2})]})

    def test_operation_and_usd_are_distinct_without_rewriting_currency(self):
        euro = self.env.ref('base.EUR')
        euro.active = True
        program = self.program(euro, 1.25)
        self.assertEqual(program.line_ids.amount_currency, 200)
        self.assertEqual(program.line_ids.amount_usd, 250)
        self.assertEqual((program.amount_currency, program.amount_usd), (200, 250))
        self.assertEqual(program.currency_id, euro)
        self.assertEqual(program.usd_currency_id, self.env.ref('base.USD'))
        with Form(program, view='step_export.view_step_export_sales_program_form') as form:
            self.assertEqual(form.amount_currency, 200)
            self.assertEqual(form.amount_usd, 250)
        self.assertEqual(program.rate_to_usd, 1.25)

    def test_effective_list_weeks_and_totals_bind_correct_currency(self):
        model = self.env['step.export.sales.program']
        listing = etree.fromstring(model.get_view(view_id=self.env.ref('step_export.view_step_export_sales_program_list').id, view_type='list')['arch'])
        self.assertFalse(listing.xpath("//field[@name='amount_currency']"))
        usd = listing.xpath("//field[@name='amount_usd']")[0]
        self.assertEqual(usd.get('string'), 'Venta USD')
        self.assertEqual(safe_eval(usd.get('options'))['currency_field'], 'usd_currency_id')
        self.assertTrue(listing.xpath("//field[@name='usd_currency_id']"))
        form = etree.fromstring(model.get_view(view_id=self.env.ref('step_export.view_step_export_sales_program_form').id, view_type='form')['arch'])
        for name, label, currency in [('amount_currency', 'Venta M Op', 'currency_id'), ('amount_usd', 'Venta USD', 'usd_currency_id')]:
            nodes = form.xpath("//field[@name='%s']" % name)
            self.assertEqual(len(nodes), 2)
            for node in nodes:
                self.assertEqual(node.get('string'), label)
                self.assertEqual(node.get('widget'), 'step_export_amount')
                options = safe_eval(node.get('options'))
                self.assertEqual(options['currency_field'], currency)
                self.assertTrue(options['no_symbol'])
