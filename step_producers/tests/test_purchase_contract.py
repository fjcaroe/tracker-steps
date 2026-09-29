from uuid import uuid4

from lxml import etree

from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "step_producers")
class TestProducerPurchaseContract(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({
            "name": "Productor contrato T30", "is_productor": True,
        })
        cls.product = cls.env["product.product"].create({
            "name": "Anticipo fruta T30", "purchase_ok": True, "type": "consu",
        })

    def _contract(self, quantity=100, scheduled=100):
        contract = self.env["step.producer.purchase.contract"].create({
            "partner_id": self.partner.id,
        })
        product_line = self.env["step.producer.purchase.contract.product"].create({
            "contract_id": contract.id, "product_id": self.product.id,
            "quantity": quantity, "uom_id": self.product.uom_po_id.id,
            "price_unit": 2,
        })
        installment = self.env["step.producer.purchase.contract.installment"].create({
            "contract_id": contract.id, "product_line_id": product_line.id,
            "quantity": scheduled, "date_due": "2026-12-15",
        })
        return contract, product_line, installment

    def test_products_and_schedule_must_reconcile(self):
        contract, product, installment = self._contract(scheduled=90)
        with self.assertRaises(ValidationError):
            contract.action_confirm()
        installment.quantity = 100
        contract.action_confirm()
        self.assertEqual(contract.state, "confirmed")
        self.assertEqual(contract.amount_total, 200)
        self.assertEqual(contract.scheduled_total, 200)
        with self.assertRaises(UserError):
            product.quantity = 101

    def test_revision_preserves_accounted_quota_and_pending_amount(self):
        contract, product, first = self._contract(quantity=100, scheduled=40)
        second = self.env["step.producer.purchase.contract.installment"].create({
            "contract_id": contract.id, "product_line_id": product.id,
            "quantity": 60, "date_due": "2027-01-15",
        })
        contract.action_confirm()
        first.state = "accounted"
        action = contract.action_revise()
        revision = contract.browse(action["res_id"])
        self.assertEqual(revision.version, 2)
        self.assertEqual(revision.parent_id, contract)
        self.assertEqual(revision.quantity_total, 60)
        self.assertEqual(revision.scheduled_total, 120)
        self.assertFalse(second.active)
        self.assertTrue(first.active)

    def test_regular_user_can_revise_but_cannot_forge_accounting_state(self):
        contract, _, _ = self._contract()
        contract.action_confirm()
        user = self.env["res.users"].with_context(no_reset_password=True).create({
            "name": "Usuario contrato T30", "login": "t30-contract-user@example.test",
            "groups_id": [(6, 0, [self.env.ref("base.group_user").id])],
        })
        with self.assertRaises(UserError):
            contract.with_user(user).write({"state": "closed"})
        with self.assertRaises(UserError):
            contract.installment_ids.with_user(user).write({"state": "accounted"})
        action = contract.with_user(user).action_revise()
        self.assertEqual(contract.browse(action["res_id"]).version, 2)

    def test_accounting_posts_once_with_balanced_entry(self):
        company = self.env.company
        debit = self.env["account.account"].create({
            "code": "T30D001", "name": "Anticipo productor T30",
            "account_type": "asset_current", "company_ids": [(6, 0, [company.id])],
        })
        credit = self.env["account.account"].create({
            "code": "T30C001", "name": "Provisión productor T30",
            "account_type": "liability_current", "company_ids": [(6, 0, [company.id])],
        })
        journal = self.env["account.journal"].create({
            "name": "Contratos productores T30", "code": uuid4().hex[:5].upper(), "type": "general",
            "company_id": company.id,
        })
        contract, product, _ = self._contract()
        product.debit_account_id = debit
        contract.write({"journal_id": journal.id, "provision_account_id": credit.id})
        contract.action_confirm()
        accountant = self.env["res.users"].with_context(no_reset_password=True).create({
            "name": "Contador contrato T30", "login": "t30-accountant@example.test",
            "groups_id": [(6, 0, [
                self.env.ref("base.group_user").id,
                self.env.ref("account.group_account_user").id,
            ])],
        })
        contract.with_user(accountant).action_account()
        move = contract.accounting_move_id
        self.assertEqual(move.state, "posted")
        self.assertEqual(sum(move.line_ids.mapped("debit")), 200)
        self.assertEqual(sum(move.line_ids.mapped("credit")), 200)
        with self.assertRaises(UserError):
            contract.with_user(accountant).action_account()

    def test_purchase_link_counts_only_confirmed_orders(self):
        contract, product_line, _ = self._contract()
        contract.action_confirm()
        order = self.env["purchase.order"].create({
            "partner_id": self.partner.id,
            "step_producer_contract_id": contract.id,
            "order_line": [(0, 0, {
                "name": "Fruta T30", "product_id": self.product.id,
                "product_qty": 25, "product_uom": self.product.uom_po_id.id,
                "price_unit": 2, "date_planned": "2026-12-01",
                "step_producer_contract_product_id": product_line.id,
            })],
        })
        self.assertEqual(product_line.ordered_quantity, 0)
        order.state = "purchase"
        self.assertEqual(product_line.ordered_quantity, 25)
        arch = self.env["step.producer.purchase.contract"].get_view(
            view_id=self.env.ref("step_producers.view_step_producer_purchase_contract_form").id,
            view_type="form")["arch"]
        pages = etree.fromstring(arch.encode()).xpath("//notebook/page/@name")
        self.assertEqual(pages[:4], ["products", "payment_schedule", "notes", "accounting"])
