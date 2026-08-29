# -*- coding: utf-8 -*-
"""Pruebas de Tesorería: conceptos, cubetas, monedas, hojas y aprobación."""

from datetime import timedelta

from odoo import Command, fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import tagged
from odoo.tools import mute_logger

from odoo.addons.account.tests.common import AccountTestInvoicingCommon

from odoo.addons.step_account_treasury.hooks import (
    _flow_type_from_code,
    archive_studio_menus,
    migrate_studio_treasury,
)


@tagged("post_install", "-at_install")
class TestTreasuryCommon(AccountTestInvoicingCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        # El usuario de las pruebas necesita el perfil completo de Tesorería.
        cls.env.user.groups_id = [Command.link(
            cls.env.ref("step_account_treasury.group_treasury_manager").id)]
        cls.Concept = cls.env["step.treasury.concept"]
        cls.Flow = cls.env["step.cashflow"]
        cls.Line = cls.env["step.cashflow.line"]
        cls.start = fields.Date.to_date("2026-09-01")

        cls.flow_currency = cls.company.currency_id
        cls.aux_currency = cls.env["res.currency"].create({
            "name": "TAX", "symbol": "T$", "rounding": 0.01,
        })
        cls.env["res.currency.rate"].create({
            "name": cls.start, "currency_id": cls.aux_currency.id,
            "company_id": cls.company.id, "rate": 2.0,
        })
        cls.third_currency = cls.env["res.currency"].create({
            "name": "TB3", "symbol": "B$", "rounding": 0.01,
        })
        cls.env["res.currency.rate"].create({
            "name": cls.start, "currency_id": cls.third_currency.id,
            "company_id": cls.company.id, "rate": 4.0,
        })

        cls.bank_journal = cls.company_data["default_journal_bank"]
        cls.concept_customer = cls.Concept.create({
            "name": "Clientes por cobrar", "code": "10", "flow_type": "inflow",
            "suggested_sheet": "customer", "company_id": cls.company.id,
        })
        cls.concept_other_income = cls.Concept.create({
            "name": "Otras recaudaciones", "code": "13", "flow_type": "inflow",
            "suggested_sheet": "other_income", "company_id": cls.company.id,
        })
        cls.concept_other_payment = cls.Concept.create({
            "name": "Otros pagos", "code": "24", "flow_type": "outflow",
            "suggested_sheet": "other_payment", "company_id": cls.company.id,
        })

    # ------------------------------------------------------------------
    # Utilidades
    # ------------------------------------------------------------------
    def _flow(self, **values):
        base = {
            "start_date": self.start,
            "company_id": self.company.id,
            "currency_id": self.flow_currency.id,
            "aux_currency_id": self.aux_currency.id,
            "journal_ids": [Command.set(self.bank_journal.ids)],
        }
        base.update(values)
        return self.Flow.create(base)

    def _invoice(self, move_type, due, amount, partner=None, currency=None, post=True):
        invoice = self.env["account.move"].create({
            "move_type": move_type,
            "partner_id": (partner or self.partner_a).id,
            "invoice_date": self.start - timedelta(days=10),
            "date": self.start - timedelta(days=10),
            "invoice_date_due": due,
            # Sin plazo de pago para que el vencimiento sea exactamente el
            # que fija la prueba y no el que derive el término del partner.
            "invoice_payment_term_id": False,
            "currency_id": (currency or self.flow_currency).id,
            "invoice_line_ids": [Command.create({
                "name": "Servicio", "quantity": 1, "price_unit": amount, "tax_ids": [],
            })],
        })
        if post:
            invoice.action_post()
        return invoice

    def _manual_line(self, flow, sheet, amount, due, concept=None, currency=None):
        return self.Line.create({
            "cashflow_id": flow.id, "sheet": sheet, "is_manual": True,
            "concept_id": (concept or self.concept_other_income).id,
            "partner_id": self.partner_a.id,
            "doc_number": "MAN-%s" % sheet, "doc_date": self.start,
            "due_date": due, "currency_id": (currency or self.flow_currency).id,
            "amount_origin": amount,
        })


@tagged("post_install", "-at_install")
class TestTreasuryConcept(TestTreasuryCommon):
    """1. Concepto con varias cuentas y restricción multiempresa."""

    def test_concept_accepts_several_accounts(self):
        accounts = self.env["account.account"].search(
            [("company_ids", "in", self.company.id)], limit=3)
        self.assertTrue(len(accounts) >= 2)
        self.concept_customer.write({"account_ids": [Command.set(accounts.ids)]})
        self.assertEqual(len(self.concept_customer.account_ids), len(accounts))

    def test_concept_rejects_account_of_another_company(self):
        other = self.env["res.company"].create({"name": "Tesorería Otra SpA"})
        foreign = self.env["account.account"].with_company(other).create({
            "code": "TREAS1", "name": "Cuenta ajena", "account_type": "asset_current",
        })
        with self.assertRaises(ValidationError):
            self.concept_customer.write({"account_ids": [Command.link(foreign.id)]})

    def test_concept_code_is_unique_per_company(self):
        with self.assertRaises(Exception), mute_logger("odoo.sql_db"):
            with self.env.cr.savepoint():
                self.Concept.create({
                    "name": "Duplicado", "code": "10", "flow_type": "inflow",
                    "company_id": self.company.id,
                })

    def test_concept_sheet_must_match_sign(self):
        with self.assertRaises(ValidationError):
            self.Concept.create({
                "name": "Incoherente", "code": "99", "flow_type": "inflow",
                "suggested_sheet": "vendor", "company_id": self.company.id,
            })

    def test_studio_code_maps_to_flow_type(self):
        self.assertEqual(_flow_type_from_code("01"), "opening")
        self.assertEqual(_flow_type_from_code("10"), "inflow")
        self.assertEqual(_flow_type_from_code("14"), "inflow")
        self.assertEqual(_flow_type_from_code("21"), "outflow")
        self.assertEqual(_flow_type_from_code("26"), "outflow")

    def test_studio_migration_is_idempotent(self):
        """2. La migración se puede repetir sin duplicar."""
        before = self.Concept.with_context(active_test=False).search_count([])
        first = migrate_studio_treasury(self.env)
        middle = self.Concept.with_context(active_test=False).search_count([])
        second = migrate_studio_treasury(self.env)
        after = self.Concept.with_context(active_test=False).search_count([])
        self.assertEqual(middle, after, "La segunda pasada no debe crear conceptos.")
        self.assertEqual(first["conceptos_studio"], second["conceptos_studio"])
        self.assertGreaterEqual(middle, before)


@tagged("post_install", "-at_install")
class TestTreasuryBuckets(TestTreasuryCommon):
    """9 y 10. Límites exactos de las cubetas y política de indefinidos."""

    def test_bucket_boundaries(self):
        flow = self._flow()
        cases = [
            (self.start - timedelta(days=1), "overdue"),
            (self.start, "w1"),
            (self.start + timedelta(days=6), "w1"),
            (self.start + timedelta(days=7), "w2"),
            (self.start + timedelta(days=13), "w2"),
            (self.start + timedelta(days=14), "w3"),
            (self.start + timedelta(days=20), "w3"),
            (self.start + timedelta(days=21), "w4"),
            (self.start + timedelta(days=27), "w4"),
            (self.start + timedelta(days=28), "w5"),
            (self.start + timedelta(days=34), "w5"),
            (self.start + timedelta(days=35), "other"),
        ]
        for due, expected in cases:
            self.assertEqual(flow._bucket_for_date(due), expected,
                             "Vencimiento %s debería caer en %s" % (due, expected))

    def test_horizon_is_five_weeks(self):
        flow = self._flow()
        self.assertEqual(flow.end_date, self.start + timedelta(days=34))

    def test_undated_policy_is_visible_and_applied(self):
        flow = self._flow()
        self.assertEqual(flow.undated_policy, "other")
        self.assertEqual(flow._bucket_for_date(False), "other")
        flow.undated_policy = "w1"
        self.assertEqual(flow._bucket_for_date(False), "w1")


@tagged("post_install", "-at_install")
class TestTreasuryCurrency(TestTreasuryCommon):
    """11 y 12. Conversión de monedas y tasa congelada."""

    def test_conversion_with_odoo_rates(self):
        flow = self._flow(rate_policy="odoo", rate_date=self.start)
        line = self._manual_line(flow, "other_income", 100.0, self.start,
                                 currency=self.aux_currency)
        # Tasa 2.0 -> 100 en moneda auxiliar equivalen a 50 en moneda del flujo.
        self.assertAlmostEqual(line.amount_flow, 50.0, places=2)

    def test_conversion_with_third_currency(self):
        flow = self._flow(rate_policy="odoo", rate_date=self.start)
        line = self._manual_line(flow, "other_income", 100.0, self.start,
                                 currency=self.third_currency)
        self.assertAlmostEqual(line.amount_flow, 25.0, places=2)
        summary = {row["code"]: row for row in flow.get_summary_rows()}
        self.assertAlmostEqual(summary["other_income"]["total_aux"], line.amount_aux, places=2)

    def test_manual_rate_follows_the_functional_document(self):
        flow = self._flow(rate_policy="manual", manual_rate=900.0)
        line = self._manual_line(flow, "other_income", 550.35, self.start,
                                 currency=self.aux_currency)
        self.assertAlmostEqual(line.amount_flow, 495315.0, places=0)
        self.assertAlmostEqual(line.amount_aux, 550.35, places=2)

    def test_rate_is_frozen_on_approved_flow(self):
        flow = self._flow(rate_policy="manual", manual_rate=900.0)
        self._manual_line(flow, "other_income", 100.0, self.start,
                          currency=self.aux_currency)
        flow.action_start()
        flow.action_approve()
        frozen = flow.applied_rate
        self.assertAlmostEqual(frozen, 900.0, places=2)
        # Cambiar la tasa de mercado no puede alterar el snapshot aprobado.
        self.env["res.currency.rate"].create({
            "name": self.start + timedelta(days=1), "currency_id": self.aux_currency.id,
            "company_id": self.company.id, "rate": 10.0,
        })
        flow.invalidate_recordset()
        self.assertAlmostEqual(flow.applied_rate, frozen, places=2)
        self.assertAlmostEqual(flow.line_ids[0].amount_flow, 90000.0, places=0)

    def test_manual_rate_records_who_and_when(self):
        flow = self._flow(rate_policy="manual", manual_rate=900.0,
                          manual_rate_reason="Presupuesto aprobado")
        flow.write({"manual_rate": 950.0})
        self.assertEqual(flow.manual_rate_uid, self.env.user)
        self.assertTrue(flow.manual_rate_date)


@tagged("post_install", "-at_install")
class TestTreasurySheets(TestTreasuryCommon):
    """3 a 8. Las siete hojas y la idempotencia de la actualización."""

    def test_customer_invoice_open_partial_overdue(self):
        overdue = self._invoice("out_invoice", self.start - timedelta(days=5), 1000.0)
        inside = self._invoice("out_invoice", self.start + timedelta(days=3), 500.0)
        flow = self._flow()
        flow.action_refresh()
        lines = flow.line_customer_ids
        self.assertEqual(len(lines), 2)
        by_bucket = {line.bucket: line.amount_flow for line in lines}
        self.assertAlmostEqual(by_bucket["overdue"], 1000.0, places=2)
        self.assertAlmostEqual(by_bucket["w1"], 500.0, places=2)
        for line in lines:
            self.assertEqual(line.source_model, "account.move")
            self.assertFalse(line.is_manual)

    def test_customer_credit_note_reduces_the_inflow(self):
        self._invoice("out_invoice", self.start + timedelta(days=3), 1000.0)
        refund = self._invoice("out_refund", self.start + timedelta(days=3), 300.0)
        flow = self._flow()
        flow.action_refresh()
        total = sum(flow.line_customer_ids.mapped("amount_flow"))
        self.assertAlmostEqual(total, 700.0, places=2)

    def test_installments_produce_one_line_per_due_date(self):
        terms = self.env["account.payment.term"].create({
            "name": "Dos cuotas Tesorería",
            "line_ids": [
                Command.create({"value": "percent", "value_amount": 50.0, "nb_days": 0}),
                Command.create({"value": "percent", "value_amount": 50.0, "nb_days": 30}),
            ],
        })
        invoice = self.env["account.move"].create({
            "move_type": "out_invoice",
            "partner_id": self.partner_a.id,
            "invoice_date": self.start,
            "date": self.start,
            "invoice_payment_term_id": terms.id,
            "currency_id": self.flow_currency.id,
            "invoice_line_ids": [Command.create({
                "name": "Cuotas", "quantity": 1, "price_unit": 1000.0, "tax_ids": []})],
        })
        invoice.action_post()
        flow = self._flow()
        flow.action_refresh()
        lines = flow.line_customer_ids.filtered(lambda l: l.doc_number == invoice.name)
        self.assertEqual(len(lines), 2, "Cada cuota debe generar su propia línea.")
        self.assertEqual(len({line.due_date for line in lines}), 2)
        self.assertAlmostEqual(sum(lines.mapped("amount_flow")), 1000.0, places=2)

    def test_vendor_bill_is_an_outflow(self):
        self._invoice("in_invoice", self.start + timedelta(days=10), 800.0,
                      partner=self.partner_b)
        flow = self._flow()
        flow.action_refresh()
        lines = flow.line_vendor_ids
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines.flow_type, "outflow")
        self.assertAlmostEqual(lines.amount_flow, 800.0, places=2)
        self.assertEqual(lines.bucket, "w2")

    def test_sale_order_counts_only_the_uninvoiced_part(self):
        order = self.env["sale.order"].create({
            "partner_id": self.partner_a.id,
            "treasury_due_date": self.start + timedelta(days=8),
            "order_line": [Command.create({
                "product_id": self.product_a.id, "product_uom_qty": 10,
                "price_unit": 100.0, "tax_id": [],
            })],
        })
        order.action_confirm()
        flow = self._flow()
        flow.action_refresh()
        line = flow.line_sale_order_ids
        self.assertEqual(len(line), 1)
        self.assertAlmostEqual(line.amount_flow, 1000.0, places=2)
        # Se factura la mitad: la proyección debe bajar a la mitad, sin duplicar.
        order.order_line.qty_delivered = 10
        invoice = order._create_invoices()
        invoice.invoice_line_ids.quantity = 5
        invoice.action_post()
        flow.action_refresh()
        line = flow.line_sale_order_ids
        self.assertAlmostEqual(line.amount_flow, 500.0, places=2)

    def test_purchase_order_counts_only_the_uninvoiced_part(self):
        order = self.env["purchase.order"].create({
            "partner_id": self.partner_b.id,
            "treasury_due_date": self.start + timedelta(days=15),
            "order_line": [Command.create({
                "product_id": self.product_a.id, "product_qty": 4,
                "price_unit": 250.0, "taxes_id": [],
                "name": "Compra", "date_planned": fields.Datetime.now(),
            })],
        })
        order.button_confirm()
        flow = self._flow()
        flow.action_refresh()
        line = flow.line_purchase_order_ids
        self.assertEqual(len(line), 1)
        self.assertAlmostEqual(line.amount_flow, 1000.0, places=2)
        self.assertEqual(line.bucket, "w3")
        order.order_line.qty_received = 4
        order.action_create_invoice()
        bill = order.invoice_ids
        bill.invoice_date = self.start
        bill.invoice_line_ids.quantity = 2
        bill.action_post()
        flow.action_refresh()
        self.assertAlmostEqual(flow.line_purchase_order_ids.amount_flow, 500.0, places=2)

    def test_proforma_disappears_once_invoiced(self):
        proforma = self.env["step.vendor.proforma"].create({
            "partner_id": self.partner_b.id,
            "company_id": self.company.id,
            "currency_id": self.flow_currency.id,
            "date": self.start,
            "date_due": self.start + timedelta(days=5),
            "line_ids": [Command.create({
                "name": "Anticipo", "quantity": 1, "price_unit": 1080.0})],
        })
        proforma.action_approve()
        flow = self._flow()
        flow.action_refresh()
        self.assertEqual(len(flow.line_proforma_ids), 1)
        self.assertAlmostEqual(flow.line_proforma_ids.amount_flow, 1080.0, places=2)
        proforma.action_mark_invoiced()
        flow.action_refresh()
        self.assertEqual(len(flow.line_proforma_ids), 0)

    def test_manual_lines_survive_a_refresh(self):
        """8. Las líneas manuales no se pierden al actualizar."""
        flow = self._flow()
        manual = self._manual_line(flow, "other_income", 1800.0,
                                   self.start + timedelta(days=2))
        adjusted = self._manual_line(flow, "other_payment", 4000.0,
                                     self.start + timedelta(days=30),
                                     concept=self.concept_other_payment)
        self._invoice("out_invoice", self.start + timedelta(days=3), 500.0)
        flow.action_refresh()
        self.assertTrue(manual.exists())
        self.assertTrue(adjusted.exists())
        self.assertAlmostEqual(manual.amount_flow, 1800.0, places=2)
        self.assertEqual(len(flow.line_customer_ids), 1)

    def test_refresh_is_idempotent(self):
        """15. Actualizar dos veces no duplica ni cambia cifras."""
        self._invoice("out_invoice", self.start + timedelta(days=3), 500.0)
        self._invoice("in_invoice", self.start + timedelta(days=3), 200.0,
                      partner=self.partner_b)
        flow = self._flow()
        flow.action_refresh()
        first = len(flow.line_ids), flow.total_inflow, flow.total_outflow
        flow.action_refresh()
        second = len(flow.line_ids), flow.total_inflow, flow.total_outflow
        self.assertEqual(first, second)

    def test_duplicated_source_is_rejected(self):
        """15. Restricción de fuente duplicada."""
        invoice = self._invoice("out_invoice", self.start + timedelta(days=3), 500.0)
        flow = self._flow()
        flow.action_refresh()
        original = flow.line_customer_ids[0]
        with self.assertRaises(Exception), mute_logger("odoo.sql_db"):
            with self.env.cr.savepoint():
                self.Line.create({
                    "cashflow_id": flow.id, "sheet": "customer",
                    "source_model": original.source_model,
                    "source_id": original.source_id,
                    "source_line_id": original.source_line_id,
                    "currency_id": self.flow_currency.id, "amount_origin": 1.0,
                })

    def test_manual_adjustment_is_protected_on_refresh(self):
        self._invoice("out_invoice", self.start + timedelta(days=3), 500.0)
        flow = self._flow()
        flow.action_refresh()
        line = flow.line_customer_ids[0]
        line.write({"amount_origin": 123.0, "adjust_reason": "Acuerdo con el cliente"})
        flow.action_refresh()
        line.invalidate_recordset()
        self.assertAlmostEqual(line.amount_origin, 123.0, places=2)


@tagged("post_install", "-at_install")
class TestTreasurySummary(TestTreasuryCommon):
    """13, 14 y 19. Saldo inicial, fórmula acumulada y exportación."""

    def _post_opening(self, journal, amount, date):
        move = self.env["account.move"].create({
            "journal_id": journal.id,
            "date": date,
            "line_ids": [
                Command.create({"account_id": journal.default_account_id.id,
                                "debit": amount, "credit": 0.0, "name": "Apertura"}),
                Command.create({"account_id": self.company_data["default_account_revenue"].id,
                                "debit": 0.0, "credit": amount, "name": "Contrapartida"}),
            ],
        })
        move.action_post()
        return move

    def test_opening_balance_adds_two_banks_and_respects_the_cutoff(self):
        second = self.env["account.journal"].create({
            "name": "Banco Tesorería 2", "code": "TBK2", "type": "bank",
            "company_id": self.company.id,
        })
        self._post_opening(self.bank_journal, 6000000.0, self.start - timedelta(days=1))
        self._post_opening(second, 4000000.0, self.start - timedelta(days=2))
        # Movimiento del propio día de inicio: NO debe contarse en la apertura.
        self._post_opening(self.bank_journal, 999.0, self.start)
        flow = self._flow(journal_ids=[Command.set((self.bank_journal | second).ids)])
        self.assertAlmostEqual(flow.opening_balance, 10000000.0, places=2)
        detail = flow._opening_balance_detail()
        self.assertEqual(len(detail), 2, "Debe haber drill-down por diario.")
        self.assertAlmostEqual(sum(row["amount"] for row in detail), 10000000.0, places=2)

    def test_accumulated_formula_matches_the_functional_example(self):
        """14. saldo final = saldo anterior + ingresos - egresos, por cubeta."""
        flow = self._flow(rate_policy="manual", manual_rate=900.0)
        flow.opening_balance = 10000000.0
        data = [
            ("customer", 595315.0, self.start - timedelta(days=1)),
            ("sale_order", 830000.0, self.start + timedelta(days=1)),
            ("other_income", 1800000.0, self.start + timedelta(days=2)),
            ("other_income", 1000000.0, self.start + timedelta(days=15)),
            ("vendor", 370108.0, self.start - timedelta(days=1)),
            ("purchase_order", 630000.0, self.start + timedelta(days=1)),
            ("proforma", 1080000.0, self.start + timedelta(days=3)),
            ("other_payment", 200000.0, self.start + timedelta(days=1)),
            ("other_payment", 2400000.0, self.start + timedelta(days=8)),
            ("other_payment", 1000000.0, self.start + timedelta(days=15)),
            ("other_payment", 4000000.0, self.start + timedelta(days=30)),
        ]
        for sheet, amount, due in data:
            concept = self.concept_other_income if sheet in (
                "customer", "sale_order", "other_income") else self.concept_other_payment
            self._manual_line(flow, sheet, amount, due, concept=concept)
        matrix = flow._summary_matrix()
        expected_closing = {
            "overdue": 10225207.0, "w1": 10945207.0, "w2": 8545207.0,
            "w3": 8545207.0, "w4": 8545207.0, "w5": 4545207.0, "other": 4545207.0,
        }
        for bucket, value in expected_closing.items():
            self.assertAlmostEqual(matrix["closing"][bucket], value, places=0,
                                   msg="Saldo acumulado incorrecto en %s" % bucket)
        self.assertAlmostEqual(flow.closing_balance, 4545207.0, places=0)
        self.assertAlmostEqual(flow.min_balance, 4545207.0, places=0)

    def test_opening_balance_enters_only_once(self):
        flow = self._flow()
        flow.opening_balance = 1000.0
        self._manual_line(flow, "other_income", 100.0, self.start)
        matrix = flow._summary_matrix()
        self.assertAlmostEqual(matrix["closing"]["overdue"], 1000.0, places=2)
        self.assertAlmostEqual(matrix["closing"]["w1"], 1100.0, places=2)
        self.assertAlmostEqual(matrix["closing"]["other"], 1100.0, places=2)

    def test_excluded_line_does_not_add_up(self):
        flow = self._flow()
        line = self._manual_line(flow, "other_income", 500.0, self.start)
        self.assertAlmostEqual(flow.total_inflow, 500.0, places=2)
        line.excluded = True
        flow.invalidate_recordset()
        self.assertAlmostEqual(flow.total_inflow, 0.0, places=2)

    def test_negative_cash_alert(self):
        flow = self._flow()
        flow.opening_balance = 100.0
        self._manual_line(flow, "other_payment", 500.0, self.start,
                          concept=self.concept_other_payment)
        flow.invalidate_recordset()
        self.assertTrue(flow.has_negative_cash)
        self.assertLess(flow.min_balance, 0.0)

    def test_export_matches_the_interface(self):
        """19. La exportación cuadra con el resumen en pantalla."""
        flow = self._flow()
        flow.opening_balance = 1000.0
        self._manual_line(flow, "other_income", 300.0, self.start)
        self._manual_line(flow, "other_payment", 100.0, self.start,
                          concept=self.concept_other_payment)
        header, rows = flow._export_matrix()
        summary = {row["label"]: row for row in flow.get_summary_rows()}
        for values in rows:
            label = values[0]
            self.assertIn(label, summary)
            self.assertAlmostEqual(values[-1] if not flow.aux_currency_id else values[-2],
                                   summary[label]["total"], places=2)
        self.assertTrue(flow.summary_html)


@tagged("post_install", "-at_install")
class TestTreasuryGovernance(TestTreasuryCommon):
    """16, 17, 18 y 20. Aprobación, permisos y multiempresa."""

    def test_approved_flow_is_locked_and_reopen_is_audited(self):
        flow = self._flow()
        self._manual_line(flow, "other_income", 100.0, self.start)
        flow.action_start()
        flow.action_approve()
        self.assertEqual(flow.state, "approved")
        self.assertTrue(flow.approved_uid and flow.approved_date)
        with self.assertRaises(UserError):
            flow.action_refresh()
        with self.assertRaises(UserError):
            flow.write({"start_date": self.start + timedelta(days=1)})
        with self.assertRaises(UserError):
            self._manual_line(flow, "other_income", 50.0, self.start)
        line = flow.line_ids[0]
        with self.assertRaises(UserError):
            line.write({"amount_origin": 999.0})
        with self.assertRaises(UserError):
            line.unlink()
        with self.assertRaises(UserError):
            flow.write({"aux_currency_id": False})
        messages_before = len(flow.message_ids)
        flow.action_reopen()
        self.assertEqual(flow.state, "in_progress")
        self.assertGreater(len(flow.message_ids), messages_before,
                           "La reapertura debe dejar mensaje de auditoría.")

    def test_reader_cannot_write(self):
        reader = self.env["res.users"].create({
            "name": "Lector Tesorería", "login": "treasury_reader_qa",
            "company_id": self.company.id, "company_ids": [Command.set([self.company.id])],
            "groups_id": [Command.set([
                self.env.ref("base.group_user").id,
                self.env.ref("step_account_treasury.group_treasury_reader").id,
            ])],
        })
        flow = self._flow()
        readable = self.Flow.with_user(reader).browse(flow.id)
        self.assertTrue(readable.name)
        with self.assertRaises(AccessError):
            readable.write({"responsible_id": reader.id})

    def test_operator_cannot_approve_without_the_group(self):
        operator = self.env["res.users"].create({
            "name": "Operador Tesorería", "login": "treasury_user_qa",
            "company_id": self.company.id, "company_ids": [Command.set([self.company.id])],
            "groups_id": [Command.set([
                self.env.ref("base.group_user").id,
                self.env.ref("step_account_treasury.group_treasury_user").id,
            ])],
        })
        flow = self._flow(approver_id=self.env.user.id)
        self._manual_line(flow, "other_income", 100.0, self.start)
        flow.action_start()
        with self.assertRaises(UserError):
            flow.with_user(operator).action_approve()

    def test_another_approver_cannot_approve_an_assigned_flow(self):
        approver = self.env["res.users"].create({
            "name": "Otro aprobador", "login": "treasury_other_approver_qa",
            "company_id": self.company.id,
            "company_ids": [Command.set([self.company.id])],
            "groups_id": [Command.set([
                self.env.ref("base.group_user").id,
                self.env.ref("step_account_treasury.group_treasury_approver").id,
            ])],
        })
        flow = self._flow(approver_id=self.env.user.id)
        self._manual_line(flow, "other_income", 100.0, self.start)
        flow.action_start()
        with self.assertRaises(UserError):
            flow.with_user(approver).action_approve()

    def test_studio_archive_is_scoped_to_the_treasury_prototype(self):
        target = self.env["ir.ui.menu"].create({"name": "Tesorería"})
        unrelated = self.env["ir.ui.menu"].create({"name": "Flujo de Caja"})
        self.env["ir.model.data"].create({
            "module": "studio_customization",
            "name": "contabilidad_tesoreria_qa",
            "model": "ir.ui.menu", "res_id": target.id,
        })
        self.env["ir.model.data"].create({
            "module": "studio_customization",
            "name": "otra_app_flujo_de_caja_qa",
            "model": "ir.ui.menu", "res_id": unrelated.id,
        })
        archive_studio_menus(self.env)
        self.assertFalse(target.active)
        self.assertTrue(unrelated.active)

    def test_multi_company_isolation(self):
        """18. Un usuario no ve flujos de otra compañía."""
        other = self.env["res.company"].create({"name": "Tesorería Aislada SpA"})
        outsider = self.env["res.users"].create({
            "name": "Usuario Aislado", "login": "treasury_isolated_qa",
            "company_id": other.id, "company_ids": [Command.set([other.id])],
            "groups_id": [Command.set([
                self.env.ref("base.group_user").id,
                self.env.ref("step_account_treasury.group_treasury_manager").id,
            ])],
        })
        flow = self._flow()
        visible = self.Flow.with_user(outsider).search([("id", "=", flow.id)])
        self.assertFalse(visible, "El flujo de otra compañía no debe ser visible.")
        concepts = self.Concept.with_user(outsider).search([("id", "=", self.concept_customer.id)])
        self.assertFalse(concepts)

    def test_flow_name_is_sequenced(self):
        flow = self._flow()
        self.assertNotEqual(flow.name, "Nuevo")
        self.assertTrue(flow.name)

    def test_menu_and_actions_are_installed(self):
        """20. La instalación deja el menú y las acciones en su sitio."""
        for xmlid in (
            "step_account_treasury.menu_treasury_root",
            "step_account_treasury.menu_treasury_cashflow",
            "step_account_treasury.menu_treasury_concept",
            "step_account_treasury.action_cashflow",
            "step_account_treasury.action_treasury_concept",
        ):
            self.assertTrue(self.env.ref(xmlid, raise_if_not_found=False), xmlid)
        root = self.env.ref("step_account_treasury.menu_treasury_root")
        self.assertEqual(root.parent_id, self.env.ref("account.menu_finance"))
