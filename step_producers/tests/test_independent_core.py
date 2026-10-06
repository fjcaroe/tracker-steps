from odoo.tests import TransactionCase, tagged
from odoo.exceptions import UserError
from ..models.producer_settlement import _TRANSITION


@tagged('post_install', '-at_install')
class TestIndependentProducerCore(TransactionCase):
    def test_settlement_without_export_receiver_and_legacy_ids(self):
        producer = self.env['res.partner'].create({'name': 'Productor independiente QA', 'is_productor': True})
        season = self.env['step.temporada'].create({'name': 'Temporada independiente QA'})
        species = self.env['step.especie'].create({'name': 'Fruta independiente QA', 'type_especie': 'frutal', 'group_especie': 'seco'})
        expense = self.env['account.account'].search([('company_ids', 'in', self.env.company.id), ('account_type', '=', 'expense')], limit=1)
        if not expense:
            expense = self.env['account.account'].create({'name': 'Compra fruta independiente QA', 'code': 'QAIND01', 'account_type': 'expense'})
        rate = self.env['step.export.grower.rate'].create({'name': 'Tarifa independiente QA', 'producer_id': producer.id,
            'season_id': season.id, 'species_id': species.id, 'expense_account_id': expense.id})
        settlement = self.env['step.export.producer.settlement'].create({'producer_id': producer.id,
            'season_id': season.id, 'species_id': species.id, 'rate_id': rate.id,
            'line_ids': [(0, 0, {'description': 'Detalle propio de compra', 'kg_qty': 100, 'allocated_fob_usd': 250})]})
        self.assertEqual(settlement.net_usd, 250)
        settlement.action_validate()
        self.assertEqual(settlement.state, 'validated')
        with self.assertRaises(UserError):
            settlement.with_context(_step_settlement_transition=True).write({'state': 'accounted'})
        # An already delivered historical fixture must keep its original tariff.
        settlement.with_context(_step_settlement_transition=_TRANSITION).write({'state': 'accounted'})
        settlement.action_close()
        with self.assertRaises(UserError):
            rate.write({'rate_value': 2})
        self.assertEqual(self.env.ref('step_export.action_export_producer_settlement'),
                         self.env.ref('step_producers.action_export_producer_settlement'))
        self.assertEqual(self.env.ref('step_export.action_step_export_estimate'),
                         self.env.ref('step_producers.action_step_export_estimate'))
        self.assertTrue(self.env['step.export.producer.settlement'].get_view(
            view_id=self.env.ref('step_producers.view_export_producer_settlement_form').id, view_type='form')['arch'])
