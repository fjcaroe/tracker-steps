# -*- coding: utf-8 -*-

import base64
import io
import zipfile

from odoo import Command, fields
from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged("post_install", "-at_install")
class TestTreasuryBatchReview(AccountTestInvoicingCommon):

    def test_adapter_is_disabled_until_a_bank_format_is_approved(self):
        adapter = self.env["step.treasury.bank.export.adapter"]
        self.assertFalse(adapter.adapter_metadata()["enabled"])
        with self.assertRaises(UserError):
            adapter.export_bank_file(self.env["account.batch.payment"])

    def test_internal_review_is_explicitly_not_a_bank_file(self):
        journal = self.company_data["default_journal_bank"]
        method_line = journal.outbound_payment_method_line_ids[:1]
        self.assertTrue(method_line)
        payment = self.env["account.payment"].create({
            "payment_type": "outbound",
            "partner_type": "supplier",
            "partner_id": self.partner_b.id,
            "amount": 1234.5,
            "date": fields.Date.today(),
            "journal_id": journal.id,
            "payment_method_line_id": method_line.id,
        })
        batch = self.env["account.batch.payment"].create({
            "batch_type": "outbound",
            "date": fields.Date.today(),
            "journal_id": journal.id,
            "payment_ids": [Command.set(payment.ids)],
        })
        action = batch.action_export_treasury_review_csv()
        attachment_id = int(action["url"].split("/web/content/")[1].split("?")[0])
        attachment = self.env["ir.attachment"].browse(attachment_id)
        payload = base64.b64decode(attachment.datas).decode("utf-8-sig")
        self.assertIn("NO CARGABLE AL BANCO", payload)
        self.assertIn("1234.50", payload)
        self.assertTrue(payload.endswith("\r\n"))

    def test_empty_batch_is_rejected(self):
        journal = self.company_data["default_journal_bank"]
        batch = self.env["account.batch.payment"].create({
            "batch_type": "outbound",
            "date": fields.Date.today(),
            "journal_id": journal.id,
        })
        with self.assertRaises(UserError):
            batch.action_export_treasury_review_csv()

    def _bancoestado_batch(self, bank_code="012", method="01"):
        journal = self.company_data["default_journal_bank"]
        partner = self.partner_a
        partner.write({"vat": "76.123.456-7", "email": "pagos@example.cl"})
        bank = self.env["res.bank"].create({"name": "Banco exportación", "bic": bank_code})
        partner_bank = self.env["res.partner.bank"].create({
            "partner_id": partner.id, "bank_id": bank.id,
            "acc_number": "00123456789", "step_bancoestado_payment_method": method,
        })
        method_line = journal.outbound_payment_method_line_ids[:1]
        payment = self.env["account.payment"].create({
            "payment_type": "outbound", "partner_type": "supplier",
            "partner_id": partner.id, "amount": 125000, "date": fields.Date.today(),
            "journal_id": journal.id, "payment_method_line_id": method_line.id,
            "partner_bank_id": partner_bank.id,
        })
        batch = self.env["account.batch.payment"].create({
            "batch_type": "outbound", "date": fields.Date.today(),
            "journal_id": journal.id, "payment_ids": [Command.set(payment.ids)],
        })
        return batch

    def test_bancoestado_export_is_real_xlsx_with_seven_columns(self):
        batch = self._bancoestado_batch()
        action = batch.action_export_bancoestado_xlsx()
        attachment_id = int(action["url"].split("/web/content/")[1].split("?")[0])
        payload = base64.b64decode(self.env["ir.attachment"].browse(attachment_id).datas)
        self.assertTrue(payload.startswith(b"PK"))
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            shared = archive.read("xl/sharedStrings.xml").decode()
        self.assertIn("MONTO DEL PAGO", shared)
        self.assertIn("761234567", shared)
        self.assertIn("00123456789", shared)

    def test_savings_method_rejects_non_bancoestado(self):
        batch = self._bancoestado_batch(bank_code="037", method="02")
        with self.assertRaises(UserError):
            batch.action_export_bancoestado_xlsx()

    def test_bank_code_must_have_three_digits(self):
        batch = self._bancoestado_batch(bank_code="INVALIDO")
        with self.assertRaises(UserError):
            batch.action_export_bancoestado_xlsx()
