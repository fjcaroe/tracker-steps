from odoo import Command
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestContractCashflow(TransactionCase):
    def test_contract_appears_once_under_concept_22_and_revision_retires_old(self):
        company = self.env.company
        concept = self.env['step.treasury.concept'].search([('company_id', '=', company.id), ('code', '=', '22')], limit=1)
        if not concept:
            concept = self.env['step.treasury.concept'].create({'name': 'Órdenes de compra', 'code': '22', 'flow_type': 'outflow', 'company_id': company.id})
        c = self.env['step.management.purchase.contract'].create({
            'partner_id': self.env['res.partner'].create({'name': 'T30 Flow Supplier'}).id,
            'installment_ids': [Command.create({'product_id': self.env['product.product'].create({'name': 'T30 Flow Product'}).id,
                'quantity': 10, 'price_unit': 3, 'date_due': '2026-11-30'})]})
        c.action_confirm()
        c.installment_ids.action_approve()
        flow = self.env['step.cashflow'].create({})
        rows = [v for v in flow._collect_purchase_order() if v['source_model'] == c._name and v['source_id'] == c.id]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['amount_origin'], 30)
        self.assertEqual(rows[0]['concept_id'], concept.id)
        c.action_revise()
        rows = [v for v in flow._collect_purchase_order() if v['source_model'] == c._name and v['source_id'] == c.id]
        self.assertEqual(rows, [])
