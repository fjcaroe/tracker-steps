# -*- coding: utf-8 -*-

import base64

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
