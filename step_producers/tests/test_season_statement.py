from odoo import fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install', 'step_producers')
class TestSeasonStatement(TransactionCase):
    def setUp(self):
        super().setUp()
        self.producer = self.env['res.partner'].create({'name': 'Productor consolidado QA', 'is_productor': True})
        self.receiver = self.env['res.partner'].create({'name': 'Recibidor consolidado QA'})
        self.season = self.env['step.temporada'].create({'name': 'Temporada consolidado QA'})
        self.species = self.env['step.especie'].create({'name': 'Cereza consolidado QA', 'type_especie': 'frutal', 'group_especie': 'seco'})
        self.product = self.env['product.product'].create({'name': 'Caja consolidado QA', 'grupo_labor': 'pack'})
        self.program = self.env['step.export.sales.program'].create({
            'name': 'Programa consolidado QA', 'partner_id': self.receiver.id, 'season_id': self.season.id,
            'species_id': self.species.id, 'product_id': self.product.id,
            'package_type_id': self.env['stock.package.type'].create({'name': 'Pallet consolidado QA'}).id,
            'date_start': '2026-11-01', 'date_end': '2026-12-31', 'rate_to_usd': 1,
        })
        account = self.env['account.account'].search([('company_ids', 'in', self.env.company.id), ('account_type', '=', 'expense')], limit=1)
        self.rate = self.env['step.export.grower.rate'].create({
            'name': 'Tarifa consolidado QA', 'producer_id': self.producer.id, 'season_id': self.season.id,
            'species_id': self.species.id, 'expense_account_id': account.id,
        })

    def _settlement(self, number, amount):
        receiver = self.env['step.export.receiver.settlement'].create({
            'receiver_id': self.receiver.id, 'sales_program_id': self.program.id, 'rate_to_usd': 1,
            'date': '2026-11-20',
        })
        # Fixture for an already reviewed receiver; export tests cover its invoice gates.
        receiver.state = 'validated'
        tag_vals = {'name': 'QA-CONS-%s' % number, 'is_fruit_tag': True, 'owner_id': self.producer.id}
        if 'step_tag_kind' in self.env['stock.quant.package']._fields:
            tag_vals.update({'step_tag_kind': 'E', 'step_producer_id': self.producer.id,
                'step_tag_line_ids': [(0, 0, {'producer_id': self.producer.id, 'product_id': self.product.id,
                                             'quantity': 10, 'boxes': 10, 'kilos': 50})]})
        tag = self.env['stock.quant.package'].create(tag_vals)
        if 'step_tag_kind' not in tag._fields:
            self.env['stock.quant']._update_available_quantity(self.product, self.env['stock.warehouse'].search([('company_id', '=', self.env.company.id)], limit=1).lot_stock_id, 10, package_id=tag)
            self.product.weight = 5
        settlement = self.env['step.export.producer.settlement'].create({
            'receiver_settlement_id': receiver.id, 'producer_id': self.producer.id, 'rate_id': self.rate.id,
            'line_ids': [(0, 0, {'tag_id': tag.id, 'kg_qty': 50, 'allocated_fob_usd': amount})],
        })
        settlement.action_validate()
        return settlement

    def test_season_mass_generation_totals_idempotency_and_report(self):
        first = self._settlement(1, 120)
        second = self._settlement(2, 180)
        wizard = self.env['step.producer.season.statement.wizard'].create({'season_id': self.season.id, 'producer_ids': [(6, 0, self.producer.ids)]})
        bills_before = self.env['account.move'].search_count([])
        action = wizard.action_generate()
        statement = self.env['step.producer.season.statement'].browse(action['domain'][0][2])
        self.assertEqual(statement.settlement_ids, first | second)
        self.assertEqual(statement.total_kg, 100)
        self.assertEqual(statement.net_usd, 300)
        self.assertEqual(wizard.action_generate()['domain'], action['domain'])
        self.assertEqual(self.env['account.move'].search_count([]), bills_before)
        statement.action_confirm()
        with self.assertRaises(UserError):
            statement.action_close()
        with self.assertRaises(UserError):
            statement.write({'settlement_ids': [(5, 0, 0)]})
        html, _ = self.env['ir.actions.report']._render_qweb_html('step_producers.report_season_statement', statement.ids)
        self.assertIn(b'Consolidado de temporada', html)

    def test_period_filters_do_not_include_other_seasons(self):
        self._settlement(1, 100)
        wizard = self.env['step.producer.season.statement.wizard'].create({'season_id': self.season.id, 'date_start': '2026-12-01'})
        with self.assertRaises(UserError):
            wizard.action_generate()
        wizard.write({'date_start': '2026-11-01', 'date_end': '2026-10-01'})
        with self.assertRaises(ValidationError):
            wizard.action_generate()
