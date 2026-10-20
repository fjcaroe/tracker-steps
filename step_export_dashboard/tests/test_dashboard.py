from datetime import date
from odoo import Command
from odoo.tests import TransactionCase, tagged
from odoo.exceptions import ValidationError


@tagged('post_install', '-at_install')
class DashboardCase(TransactionCase):
    def fixture(self):
        self.env = self.env(context=dict(self.env.context, tracking_disable=True,
            mail_create_nosubscribe=True, no_reset_password=True))
        self.season = self.env['step.temporada'].create({'name': 'QA T96 temporada'})
        self.species = self.env['step.especie'].create({'name': 'QA T96 cerezas', 'type_especie': 'frutal', 'group_especie': 'seco'})
        self.receiver = self.env['res.partner'].create({'name': 'QA T96 recibidor'})
        self.product = self.env['product.product'].create({'name': 'QA T96 caja', 'grupo_labor': 'pack'})
        pallet = self.env['stock.package.type'].create({'name': 'QA T96 pallet'})
        self.program = self.env['step.export.sales.program'].create({
            'name': 'QA T96 cerezas 2,5 kg', 'season_id': self.season.id, 'species_id': self.species.id,
            'partner_id': self.receiver.id, 'product_id': self.product.id, 'package_type_id': pallet.id,
            'date_start': date(2026, 10, 5), 'date_end': date(2026, 11, 30),
            'currency_id': self.env.ref('base.USD').id, 'rate_to_usd': 1,
            'pallets_per_container': 1, 'boxes_per_pallet': 10, 'kg_per_box': 10,
            'line_ids': [Command.create({'week_start': date(2026, 10, 5), 'container_qty': 1, 'price_per_kg': 6}),
                         Command.create({'week_start': date(2026, 11, 2), 'container_qty': 2, 'price_per_kg': 5})]})
        self.program.action_validate(); self.program.action_activate()
        self.shipment = self.env['step.export.export'].create({
            'name': 'QA T96 embarque', 'date': date(2026, 10, 7),
            'season_id': self.season.id, 'species_id': self.species.id, 'sales_program_id': self.program.id,
            'line_ids': [Command.create({'product_id': self.product.id, 'pallet_qty': 1,
                                        'boxes_per_pallet': 10, 'kg_per_box': 11.5})]})
        # Controlled test fixture: no dispatch, invoice, inventory move or DTE is emitted.
        self.shipment.state = 'shipped'

    def result(self, **filters):
        return self.program.dashboard_comparison({'season_id': self.season.id, **filters})

    def test_weighted_totals_and_intersecting_filters(self):
        self.fixture()
        result = self.result()
        for group in ('species', 'programs'):
            total = result[group]['total']
            self.assertEqual((total['planned_kg'], total['planned_usd'], total['actual_kg']), (300, 1600, 115))
            self.assertAlmostEqual(total['planned_price'], 1600 / 300)
            self.assertIsNone(total['actual_usd'])
        october = self.result(month='2026-10')['species']['total']
        self.assertEqual((october['planned_kg'], october['actual_kg']), (100, 115))
        self.assertEqual(self.result(week='2026-10-05')['species']['total']['planned_kg'], 100)
        self.assertEqual(self.result(month='2026-11', week='2026-10-05')['species']['total']['planned_kg'], 0)

    def test_versions_draft_and_missing_dates(self):
        self.fixture()
        old = self.program
        new = self.env[old._name].browse(old.action_new_version()['res_id'])
        new.line_ids[0].container_qty = 2
        new.action_validate(); new.action_activate()
        draft = self.shipment.copy({'name': 'QA T96 borrador'})
        self.assertEqual(draft.state, 'draft')
        result = self.result()
        self.assertEqual(len(result['programs']['rows']), 1)
        self.assertEqual(result['programs']['total']['planned_kg'], 400)
        self.assertEqual(result['programs']['total']['actual_kg'], 115)
        self.shipment.date = False
        self.assertEqual(self.result(month='2026-10')['species']['total']['actual_kg'], 0)
        self.assertEqual(self.result()['species']['total']['actual_kg'], 115)

    def test_company_scope_and_invalid_filter(self):
        self.fixture()
        other = self.env['res.company'].create({'name': 'QA T96 otra empresa'})
        scoped = self.program.with_context(allowed_company_ids=[other.id])
        self.assertFalse(scoped.dashboard_comparison({'season_id': self.season.id})['species']['rows'])
        for filters in ({'month': '2026-13'}, {'week': '2026-10-07'}):
            with self.assertRaises(ValidationError): self.result(**filters)
        empty = self.result(month='2027-01')['species']['total']
        self.assertIsNone(empty['planned_price'])
