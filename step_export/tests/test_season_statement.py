from odoo import fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase, tagged
from ..models.step_export_settlement import _RECEIVER_TRANSITION
from odoo.addons.step_producers.migration_helpers import transfer_ownership


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
        receiver.with_context(_receiver_transition=_RECEIVER_TRANSITION).write({'state': 'validated'})
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

    def test_period_uses_shipment_date_and_species_is_part_of_scope(self):
        settlement = self._settlement(3, 100)
        receiver = settlement.receiver_settlement_id
        shipment = self.env['step.export.export'].create({'name': 'Embarque consolidado QA',
            'date': '2026-11-04', 'sales_program_id': self.program.id,
            'tag_ids': [(6, 0, settlement.line_ids.tag_id.ids)]})
        invoice = self.env['account.move'].create({'move_type': 'out_invoice', 'partner_id': self.receiver.id,
            'step_export_shipment_id': shipment.id})
        # Receiver fixture deliberately has a different date from its shipment.
        receiver.with_context(_receiver_transition=_RECEIVER_TRANSITION).write({'state': 'draft'})
        self.env['step.export.receiver.settlement.line'].create({'settlement_id': receiver.id,
            'shipment_id': shipment.id, 'invoice_id': invoice.id, 'sales_amount': 100})
        receiver.with_context(_receiver_transition=_RECEIVER_TRANSITION).write({'state': 'validated'})
        wizard = self.env['step.producer.season.statement.wizard'].create({'season_id': self.season.id,
            'species_id': self.species.id, 'date_start': '2026-11-01', 'date_end': '2026-11-10',
            'producer_ids': [(6, 0, self.producer.ids)]})
        action = wizard.action_generate()
        statement = self.env['step.producer.season.statement'].browse(action['domain'][0][2])
        self.assertEqual(statement.species_id, self.species)
        self.assertEqual(statement.settlement_ids, settlement)
        wizard.date_start = '2026-11-10'
        with self.assertRaises(UserError):
            wizard.action_generate()

    def test_historical_dimensions_backfill_keeps_ids_and_amounts(self):
        settlement = self._settlement(4, 100)
        original_id, amount, line_ids = settlement.id, settlement.net_usd, settlement.line_ids.ids
        self.env.flush_all()
        # Reproduce the old schema's missing standalone dimensions inside this
        # transaction. DDL and fixture data are rolled back by TransactionCase.
        for column in ('date', 'season_id', 'species_id'):
            self.env.cr.execute('ALTER TABLE step_export_producer_settlement ALTER COLUMN %s DROP NOT NULL' % column)
        self.env.cr.execute('UPDATE step_export_producer_settlement SET date=NULL,season_id=NULL,species_id=NULL WHERE id=%s', [settlement.id])
        transfer_ownership(self.env.cr)
        settlement.invalidate_recordset()
        self.assertEqual(settlement.id, original_id)
        self.assertEqual(settlement.line_ids.ids, line_ids)
        self.assertEqual(settlement.net_usd, amount)
        self.assertEqual(settlement.date, settlement.receiver_settlement_id.date)
        self.assertEqual(settlement.species_id, self.species)
        self.assertEqual(settlement.season_id, self.season)
