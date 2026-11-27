from odoo import Command, fields, models


class AccountMoveReversal(models.TransientModel):
    _inherit = "account.move.reversal"

    l10n_cl_is_text_correction = fields.Boolean(string="Only Text Correction")
    l10n_cl_original_text = fields.Char(string="Original Text", help="This is the text that is intended to be changed")
    l10n_cl_corrected_text = fields.Char(string="New Corrected Text", help="This is the text that should say")
    l10n_cl_edi_reference_doc_code = fields.Selection(
        selection=[("1", "1. Cancels Referenced Document"), ("2", "2. Corrects Referenced Document Text"),
                   ("3", "3. Corrects Referenced Document Amount")],
        string="SII Reference Code",
    )

    def _prepare_default_reversal(self, move):
        values = super()._prepare_default_reversal(move)
        if (self.country_code != "CL" or move.move_type != "out_invoice" or not move.l10n_latam_document_number
                or self.l10n_latam_document_type_id.internal_type != "credit_note"):
            return values
        reference = {
            "l10n_cl_reference_doc_type_id": move.l10n_latam_document_type_id.id,
            "date": move.invoice_date,
            "origin_doc_number": move.l10n_latam_document_number,
            "reference_doc_code": self.l10n_cl_edi_reference_doc_code or ("2" if self.l10n_cl_is_text_correction else "3"),
            "reason": self.reason,
        }
        values["l10n_cl_reference_ids"] = [Command.create(reference)]
        if self.l10n_cl_is_text_correction:
            description = self.env._("Where it says: %(original)s should say: %(corrected)s",
                                     original=self.l10n_cl_original_text, corrected=self.l10n_cl_corrected_text)
            values["line_ids"] = [Command.create({
                "name": description, "display_type": "product", "account_id": self.journal_id.default_account_id.id,
                "quantity": 1.0, "price_unit": 0.0, "tax_ids": [Command.clear()],
            })]
        return values
