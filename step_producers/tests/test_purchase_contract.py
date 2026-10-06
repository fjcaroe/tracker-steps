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
        cls.species = cls.env["step.especie"].create({
            "name": "Cereza T30", "type_especie": "frutal", "group_especie": "fruta_h",
        })
        cls.product = cls.env["product.product"].create({
            "name": "Anticipo fruta T30", "purchase_ok": True, "type": "consu",
            "step_export_species_id": cls.species.id, "step_export_enabled": True,
        })

    def _contract(self, quantity=100, scheduled=100):
        contract = self.env["step.producer.purchase.contract"].create({
            "partner_id": self.partner.id,
        })
        product_line = self.env["step.producer.purchase.contract.product"].create({
            "contract_id": contract.id, "product_id": self.product.id,
            "species_id": self.species.id,
            "quantity": quantity, "uom_id": self.product.uom_po_id.id,
            "price_unit": 2,
        })
        installment = self.env["step.producer.purchase.contract.installment"].create({
            "contract_id": contract.id, "product_line_id": product_line.id,
            "quantity": scheduled, "date_due": "2026-12-15",
        })
        return contract, product_line, installment

    def test_variant_price_prefers_specific_line_and_rejects_ties(self):
        contract, general, _ = self._contract()
        group = self.env["step.grupo.variedad"].create({
            "name": "Cerezas T30", "especie_id": self.species.id,
        })
        variety = self.env["step.variedad"].create({
            "name": "Santina T30", "cod_variedad": "T30S",
            "especie_id": self.species.id, "grupo_variedad_id": group.id,
        })
        category = self.env["step.packing.fruit.category"].create({"name": "Cat 1 T30"})
        model = self.env["step.producer.purchase.contract.product"]
        specific = model.create({
            "contract_id": contract.id, "product_id": self.product.id,
            "species_id": self.species.id, "variety_id": variety.id,
            "quantity": 10, "uom_id": self.product.uom_po_id.id, "price_unit": 3,
        })
        self.assertEqual(model.resolve_variant_price(
            contract, self.product, self.species, variety), specific)
        self.assertEqual(model.resolve_variant_price(
            contract, self.product, self.species), general)
        model.create({
            "contract_id": contract.id, "product_id": self.product.id,
            "species_id": self.species.id, "category_id": category.id,
            "quantity": 10, "uom_id": self.product.uom_po_id.id, "price_unit": 4,
        })
        with self.assertRaisesRegex(UserError, "igual de específicos"):
            model.resolve_variant_price(contract, self.product, self.species,
                                        variety, category)
        with self.assertRaises(ValidationError):
            model.create({
                "contract_id": contract.id, "product_id": self.product.id,
                "species_id": self.species.id, "quantity": 1,
                "uom_id": self.product.uom_po_id.id, "price_unit": 5,
            })

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
        with self.assertRaises(UserError):
            contract.product_line_ids.with_user(user).write({"debit_account_id": False})
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
        company.write({"step_producer_advance_product_id": self.product.id, "step_producer_advance_account_id": debit.id})
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

    def test_advance_account_overrides_fruit_expense_and_respects_journal(self):
        company = self.env.company
        wrong = self.env["account.account"].create({
            "code": "T30W001", "name": "Costo automático no aprobado T30",
            "account_type": "expense_direct_cost", "company_ids": [(6, 0, [company.id])],
        })
        debit = self.env["account.account"].create({
            "code": "T30A001", "name": "Contrato productor T30",
            "account_type": "asset_current", "company_ids": [(6, 0, [company.id])],
        })
        credit = self.env["account.account"].create({
            "code": "T30L001", "name": "Contrato por pagar T30",
            "account_type": "liability_current", "company_ids": [(6, 0, [company.id])],
        })
        journal = self.env["account.journal"].create({
            "name": "Contratos restringidos T30", "code": uuid4().hex[:5].upper(),
            "type": "general", "company_id": company.id,
            "account_control_ids": [(6, 0, credit.ids)],
        })
        contract, product, _ = self._contract()
        product.debit_account_id = wrong
        company.write({"step_producer_advance_product_id": self.product.id, "step_producer_advance_account_id": debit.id})
        contract.write({"journal_id": journal.id, "provision_account_id": credit.id})
        contract.action_confirm()
        with self.assertRaisesRegex(UserError, "Cuentas rechazadas"):
            contract.action_account()
        self.assertFalse(contract.accounting_move_id)
        company.write({"step_producer_advance_product_id": self.product.id, "step_producer_advance_account_id": debit.id})
        with self.assertRaisesRegex(UserError, "Cuentas rechazadas"):
            contract.action_account()
        journal.account_control_ids = [(6, 0, (credit | debit).ids)]
        contract.action_account()
        self.assertEqual(contract.accounting_move_id.state, "posted")
        self.assertEqual(set(contract.accounting_move_id.line_ids.mapped("account_id").ids),
                         set((credit | debit).ids))
        with self.assertRaises(UserError):
            product.debit_account_id = wrong

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

    def test_no_analytic_widget_and_export_products_only(self):
        contract, product, installment = self._contract()
        arch = self.env[contract._name].get_view(
            view_id=self.env.ref("step_producers.view_step_producer_purchase_contract_form").id,
            view_type="form")["arch"]
        tree = etree.fromstring(arch.encode())
        self.assertFalse(tree.xpath("//field[@name='analytic_distribution']"))
        self.assertFalse(tree.xpath("//field[@name='debit_account_id']"))
        self.assertIn("step_export_enabled", str(product._fields["product_id"].domain))
        self.assertIn(self.product.name, product.display_name)
        self.assertEqual(installment.advance_description, "Anticipo contrato " + contract.name)
        nonexport = self.env["product.product"].create({"name": "No exportable", "type": "consu"})
        with self.assertRaisesRegex(ValidationError, "Es exportación"):
            product.product_id = nonexport

    def test_company_advance_must_be_asset_and_same_company(self):
        expense = self.env["account.account"].create({
            "code": "T30EXP", "name": "Gasto fruta", "account_type": "expense",
            "company_ids": [(6, 0, self.env.company.ids)],
        })
        with self.assertRaisesRegex(ValidationError, "activo"):
            self.env.company.step_producer_advance_account_id = expense
        other = self.env["res.company"].create({"name": "Otra empresa anticipo T30"})
        asset = self.env["account.account"].create({
            "code": "T30OTHER", "name": "Anticipo otra empresa", "account_type": "asset_current",
            "company_ids": [(6, 0, other.ids)],
        })
        with self.assertRaises(ValidationError):
            self.env.company.step_producer_advance_account_id = asset
