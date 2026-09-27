# -*- coding: utf-8 -*-
"""Lotes de pago generados desde el flujo de caja."""

from datetime import timedelta

from odoo import Command, fields
from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged("post_install", "-at_install")
class TestCashflowBatch(AccountTestInvoicingCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        # El usuario de las pruebas necesita el perfil completo de Tesorería.
        cls.env.user.groups_id = [Command.link(
            cls.env.ref("step_account_treasury.group_treasury_manager").id)]
        cls.start = fields.Date.today()
        cls.journal = cls.company_data["default_journal_bank"]
        cls.method_line = cls.journal.outbound_payment_method_line_ids[:1]

        # Vencido, semana 1 y semana 4: cubren el alcance por omisión y lo que
        # queda fuera de él.
        cls.bill_overdue = cls._bill(1000.0, cls.start - timedelta(days=5))
        cls.bill_week1 = cls._bill(500.0, cls.start + timedelta(days=3))
        cls.bill_week4 = cls._bill(700.0, cls.start + timedelta(days=24))

        cls.flow = cls._flow("Flujo de prueba")

    # ------------------------------------------------------------------
    # Utilidades
    # ------------------------------------------------------------------
    @classmethod
    def _bill(cls, amount, due_date):
        """Factura de proveedor publicada con un vencimiento exacto."""
        bill = cls.env["account.move"].create({
            "move_type": "in_invoice",
            "partner_id": cls.partner_a.id,
            "invoice_date": cls.start - timedelta(days=10),
            "date": cls.start - timedelta(days=10),
            "invoice_date_due": due_date,
            # Sin plazo de pago para que el vencimiento sea el de la prueba.
            "invoice_payment_term_id": False,
            "invoice_line_ids": [Command.create({
                "name": "Servicio", "quantity": 1, "price_unit": amount, "tax_ids": [],
            })],
        })
        bill.action_post()
        return bill

    @classmethod
    def _flow(cls, name):
        flow = cls.env["step.cashflow"].create({
            "name": name,
            "company_id": cls.company.id,
            "start_date": cls.start,
            "currency_id": cls.company.currency_id.id,
            "journal_ids": [Command.set(cls.journal.ids)],
        })
        flow.action_start()
        flow.action_refresh()
        return flow

    def _line_of(self, bill, flow=None):
        flow = flow or self.flow
        line = flow.line_ids.filtered(
            lambda item: item.source_model == "account.move" and item.source_id == bill.id)
        self.assertTrue(line, "El flujo debía recolectar la factura %s." % bill.name)
        return line

    def _wizard(self, lines=None, scope="overdue_w1"):
        values = {
            "bucket_scope": scope,
            "journal_id": self.journal.id,
            "payment_method_line_id": self.method_line.id,
            "payment_date": self.start,
        }
        if lines is not None:
            values["line_ids"] = [Command.set(lines.ids)]
        return self.env["step.cashflow.batch.wizard"].with_context(
            active_model="step.cashflow", active_id=self.flow.id,
        ).create(values)

    def _create_batch(self, wizard):
        action = wizard.action_create_batch()
        self.assertEqual(action["res_model"], "account.batch.payment")
        return self.env["account.batch.payment"].browse(action["res_id"])

    # ------------------------------------------------------------------
    # Alcance
    # ------------------------------------------------------------------
    def test_default_scope_is_overdue_plus_week_one(self):
        payable = self.flow._batch_scope_lines(("overdue", "w1"))["payable"]
        self.assertIn(self._line_of(self.bill_overdue), payable)
        self.assertIn(self._line_of(self.bill_week1), payable)
        self.assertNotIn(self._line_of(self.bill_week4), payable)

    def test_wizard_preselects_the_payable_lines(self):
        wizard = self._wizard()
        self.assertEqual(wizard.cashflow_id, self.flow)
        self.assertEqual(
            set(wizard.line_ids.ids),
            set((self._line_of(self.bill_overdue) | self._line_of(self.bill_week1)).ids))
        self.assertEqual(wizard.payment_count, 2)
        self.assertAlmostEqual(wizard.amount_total, 1500.0, places=2)

    def test_whole_horizon_scope_adds_the_later_weeks(self):
        payable = self.flow._batch_scope_lines(
            ("overdue", "w1", "w2", "w3", "w4", "w5"))["payable"]
        self.assertIn(self._line_of(self.bill_week4), payable)

    def test_projections_without_invoice_are_reported_not_paid(self):
        """Una línea manual proyecta caja pero no tiene asiento que pagar."""
        manual = self.env["step.cashflow.line"].create({
            "cashflow_id": self.flow.id,
            "sheet": "other_payment",
            "is_manual": True,
            "partner_id": self.partner_a.id,
            "doc_number": "Arriendo",
            "due_date": self.start,
            "currency_id": self.company.currency_id.id,
            "amount_origin": -300.0,
        })
        report = self.flow._batch_scope_lines(("overdue", "w1"))
        self.assertIn(manual, report["no_document"])
        self.assertFalse(report["no_document"] & report["payable"])
        self.assertIn("sin factura publicada", self._wizard().skipped_note)

    def test_excluded_lines_never_reach_the_batch(self):
        self._line_of(self.bill_week1).excluded = True
        payable = self.flow._batch_scope_lines(("overdue", "w1"))["payable"]
        self.assertNotIn(self._line_of(self.bill_week1), payable)

    def test_inflow_lines_are_never_offered(self):
        customer_invoice = self.env["account.move"].create({
            "move_type": "out_invoice",
            "partner_id": self.partner_a.id,
            "invoice_date": self.start - timedelta(days=10),
            "date": self.start - timedelta(days=10),
            "invoice_date_due": self.start - timedelta(days=2),
            "invoice_payment_term_id": False,
            "invoice_line_ids": [Command.create({
                "name": "Venta", "quantity": 1, "price_unit": 800.0, "tax_ids": [],
            })],
        })
        customer_invoice.action_post()
        self.flow.action_refresh()
        report = self.flow._batch_scope_lines(("overdue", "w1"))
        self.assertTrue(self._line_of(customer_invoice))
        self.assertNotIn(self._line_of(customer_invoice), report["payable"])

    # ------------------------------------------------------------------
    # Creación del lote
    # ------------------------------------------------------------------
    def test_batch_groups_one_payment_per_invoice(self):
        batch = self._create_batch(self._wizard())

        self.assertEqual(batch.batch_type, "outbound")
        self.assertEqual(batch.journal_id, self.journal)
        self.assertEqual(len(batch.payment_ids), 2)
        self.assertAlmostEqual(sum(batch.payment_ids.mapped("amount")), 1500.0, places=2)
        self.assertEqual(batch.payment_ids.mapped("payment_method_line_id"), self.method_line)

        overdue_line = self._line_of(self.bill_overdue)
        self.assertEqual(overdue_line.treasury_batch_id, batch)
        self.assertAlmostEqual(overdue_line.treasury_payment_id.amount, 1000.0, places=2)
        self.assertIn(self.bill_overdue.payment_state, ("in_payment", "paid"))
        self.assertFalse(self._line_of(self.bill_week4).treasury_batch_id)
        self.assertEqual(self.bill_week4.payment_state, "not_paid")

    def test_selection_is_respected(self):
        """Sólo se paga lo que el usuario dejó marcado."""
        batch = self._create_batch(self._wizard(lines=self._line_of(self.bill_overdue)))
        self.assertEqual(len(batch.payment_ids), 1)
        self.assertFalse(self._line_of(self.bill_week1).treasury_batch_id)
        self.assertEqual(self.bill_week1.payment_state, "not_paid")

    def test_partial_amount_leaves_the_invoice_open(self):
        """Una cuota paga su parte: el documento conserva el saldo restante."""
        line = self._line_of(self.bill_overdue)
        line.amount_origin = -400.0
        batch = self._create_batch(self._wizard(lines=line))
        self.assertAlmostEqual(batch.payment_ids.amount, 400.0, places=2)
        self.assertAlmostEqual(abs(self.bill_overdue.amount_residual), 600.0, places=2)
        self.assertEqual(self.bill_overdue.payment_state, "partial")

    def test_amount_never_exceeds_the_real_residual(self):
        line = self._line_of(self.bill_overdue)
        line.amount_origin = -9999.0
        batch = self._create_batch(self._wizard(lines=line))
        self.assertAlmostEqual(batch.payment_ids.amount, 1000.0, places=2)

    def test_a_line_is_not_offered_twice(self):
        self._create_batch(self._wizard(lines=self._line_of(self.bill_overdue)))
        payable = self.flow._batch_scope_lines(("overdue", "w1"))["payable"]
        self.assertNotIn(self._line_of(self.bill_overdue), payable)
        self.assertIn("ya incluidas en otro lote", self._wizard().skipped_note)

    def test_empty_selection_is_rejected(self):
        wizard = self._wizard(lines=self.env["step.cashflow.line"])
        with self.assertRaises(UserError):
            wizard.action_create_batch()

    def test_payment_method_must_belong_to_the_journal(self):
        other_journal = self.env["account.journal"].create({
            "name": "Banco alterno", "type": "bank", "code": "BNK2",
            "company_id": self.company.id,
        })
        wizard = self._wizard()
        wizard.journal_id = other_journal
        with self.assertRaises(UserError):
            wizard.action_create_batch()

    def test_cancelled_flow_does_not_pay(self):
        flow = self._flow("Flujo anulado")
        flow.action_cancel()
        with self.assertRaises(UserError):
            flow.action_open_batch_wizard()

    def test_approved_flow_can_still_be_paid_and_stays_frozen(self):
        """Aprobar congela la base de cálculo, no impide ejecutar los pagos."""
        self.flow.action_approve()
        line = self._line_of(self.bill_overdue)
        batch = self._create_batch(self._wizard(lines=line))
        self.assertEqual(line.treasury_batch_id, batch)
        self.assertEqual(self.flow.state, "approved")
        with self.assertRaises(UserError):
            line.write({"amount_origin": -1.0})

    def test_line_action_requires_a_single_flow(self):
        other_flow = self._flow("Otro flujo")
        lines = self._line_of(self.bill_overdue) | self._line_of(self.bill_week1, other_flow)
        with self.assertRaises(UserError):
            lines.action_open_batch_wizard()

    def test_line_action_opens_the_wizard_with_the_selection(self):
        line = self._line_of(self.bill_overdue)
        action = line.action_open_batch_wizard()
        self.assertEqual(action["res_model"], "step.cashflow.batch.wizard")
        self.assertEqual(action["context"]["default_cashflow_id"], self.flow.id)
        self.assertEqual(action["context"]["default_line_ids"], line.ids)
