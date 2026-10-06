from uuid import uuid4

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestContractCashflow(TransactionCase):
    def _posted_contract(self, payable=False, foreign=False):
        company = self.env.company
        partner = self.env["res.partner"].create({"name": "Productor anticipo QA", "is_productor": True})
        species = self.env["step.especie"].create({"name": "Fruta anticipos QA", "type_especie": "frutal", "group_especie": "fruta_h"})
        fruit = self.env["product.product"].create({"name": "Fruta exportable QA", "type": "consu", "step_export_enabled": True})
        advance = self.env["product.product"].create({"name": "Anticipo contrato QA", "type": "service"})
        debit = self.env["account.account"].create({"code": uuid4().hex[:10], "name": "Anticipos QA", "account_type": "asset_current", "company_ids": [(6, 0, company.ids)]})
        credit = self.env["account.account"].create({"code": uuid4().hex[:10], "name": "Provisión anticipos QA", "account_type": "liability_payable" if payable else "liability_current", "reconcile": payable, "company_ids": [(6, 0, company.ids)]})
        journal = self.env["account.journal"].create({"name": "Contrato anticipos QA", "code": uuid4().hex[:5], "type": "general", "company_id": company.id})
        company.write({"step_producer_advance_product_id": advance.id, "step_producer_advance_account_id": debit.id})
        currency = company.currency_id
        if foreign:
            currency = self.env.ref("base.USD") if company.currency_id != self.env.ref("base.USD") else self.env.ref("base.EUR")
            currency.active = True
        contract = self.env["step.producer.purchase.contract"].create({"partner_id": partner.id, "currency_id": currency.id, "journal_id": journal.id, "provision_account_id": credit.id, "accounting_date": "2026-10-06"})
        product = self.env["step.producer.purchase.contract.product"].create({"contract_id": contract.id, "product_id": fruit.id, "species_id": species.id, "quantity": 100, "price_unit": 2, "uom_id": fruit.uom_id.id})
        for qty, due in [(40, "2026-10-09"), (60, "2026-10-21")]:
            self.env["step.producer.purchase.contract.installment"].create({"contract_id": contract.id, "product_line_id": product.id, "quantity": qty, "date_due": due})
        contract.action_confirm()
        contract.action_account()
        return contract, advance, debit, credit

    def _flow(self):
        return self.env["step.cashflow"].create({"start_date": "2026-10-06"})

    def test_posted_installments_are_visible_once_with_actual_due_dates(self):
        contract, advance, debit, credit = self._posted_contract()
        move = contract.accounting_move_id
        self.assertEqual(len(move.line_ids), 4)
        self.assertEqual(move.line_ids.filtered(lambda l: l.account_id == debit).mapped("product_id"), advance)
        self.assertFalse(any(move.line_ids.mapped("analytic_distribution")))
        self.assertEqual(sorted(move.line_ids.filtered(lambda l: l.account_id == credit).mapped("date_maturity")),
                         sorted(contract.installment_ids.mapped("date_due")))
        flow = self._flow()
        flow.action_refresh()
        lines = flow.line_ids.filtered(lambda l: l.source_model == contract._name and l.source_id == contract.id)
        self.assertEqual(sorted(lines.mapped("amount_origin")), [80, 120])
        self.assertEqual(sorted(lines.mapped("bucket")), ["w1", "w3"])
        flow.action_refresh()
        self.assertEqual(flow.line_ids.filtered(lambda l: l.source_model == contract._name and l.source_id == contract.id), lines)
        self.assertEqual(lines[0].action_open_source()["res_id"], contract.id)
        if "_batch_scope_lines" in dir(flow):
            self.assertFalse(lines & flow._batch_scope_lines(("w1", "w3"))["payable"])

    def test_foreign_currency_and_paid_installment(self):
        contract, _, _, _ = self._posted_contract(foreign=True)
        flow = self._flow()
        lines = [l for l in flow._collect_vendor() if l["source_model"] == contract._name and l["source_id"] == contract.id]
        self.assertEqual(sum(l["amount_origin"] for l in lines), 200)
        self.assertEqual({l["currency_id"] for l in lines}, {contract.currency_id.id})
        contract.installment_ids[0].state = "accounted"
        remaining = [l for l in flow._collect_vendor() if l["source_model"] == contract._name and l["source_id"] == contract.id]
        self.assertEqual(len(remaining), 1)
        self.assertEqual(remaining[0]["amount_origin"], 120)

    def test_partial_reversal_reduces_non_reconcilable_provision(self):
        contract, _, debit, credit = self._posted_contract()
        installment = contract.installment_ids[0]
        reverse = self.env["account.move"].create({
            "journal_id": contract.journal_id.id, "date": "2026-10-07", "partner_id": contract.partner_id.id,
            "line_ids": [(0, 0, {"account_id": credit.id, "partner_id": contract.partner_id.id, "debit": 30}),
                         (0, 0, {"account_id": debit.id, "partner_id": contract.partner_id.id, "credit": 30})],
        })
        reverse.action_post()
        installment.reversal_move_id = reverse
        rows = [l for l in self._flow()._collect_vendor() if l["source_model"] == contract._name and l["source_id"] == contract.id]
        self.assertEqual(sorted(l["amount_origin"] for l in rows), [50, 120])

    def test_unposted_and_other_company_contracts_are_not_collected(self):
        contract, _, _, _ = self._posted_contract()
        other = self.env["res.company"].create({"name": "Otra empresa flujo anticipo QA"})
        flow = self.env["step.cashflow"].with_company(other).create({"start_date": "2026-10-06", "company_id": other.id})
        self.assertFalse([l for l in flow._collect_vendor() if l["source_model"] == contract._name])
        contract.accounting_move_id.button_draft()
        self.assertFalse([l for l in self._flow()._collect_vendor() if l["source_model"] == contract._name and l["source_id"] == contract.id])

    def test_packing_menu_opens_original_tag_content(self):
        self.assertEqual(self.env.ref("step_producer_fruit_flow.menu_producer_packing_tags").action,
                         self.env.ref("step_producers_integrations.action_producer_packing_control"))
