"""Steps' LGPL adapter for invoice references and stamps already stored in a converted Chilean database."""
import base64
from io import BytesIO

from odoo import api, fields, models

from .sys_invoice_reference_labels import METADATA


class InvoiceReference(models.Model):
    _name = "l10n_cl.account.invoice.reference"
    _description = METADATA["model"]
    _rec_name = "origin_doc_number"

    origin_doc_number = fields.Char(required=True, **METADATA["origin_doc_number"])
    reference_doc_code = fields.Selection(METADATA["codes"], **METADATA["reference_doc_code"])
    l10n_cl_reference_doc_type_id = fields.Many2one("l10n_latam.document.type", ondelete="set null",
                                                    **METADATA["l10n_cl_reference_doc_type_id"])
    l10n_cl_reference_doc_internal_type = fields.Selection(related="l10n_cl_reference_doc_type_id.internal_type",
                                                          **METADATA["l10n_cl_reference_doc_internal_type"])
    reason = fields.Char(**METADATA["reason"])
    move_id = fields.Many2one("account.move", index=True, ondelete="cascade", **METADATA["move_id"])
    date = fields.Date(required=True, **METADATA["date"])


class AccountMove(models.Model):
    _inherit = "account.move"

    l10n_cl_reference_ids = fields.One2many("l10n_cl.account.invoice.reference", "move_id", copy=False,
                                            **METADATA["l10n_cl_reference_ids"])
    l10n_cl_sii_barcode = fields.Char(readonly=True, copy=False, **METADATA["l10n_cl_sii_barcode"])

    def _get_name_invoice_report(self):
        self.ensure_one()
        if self.l10n_latam_use_documents and self.company_id.account_fiscal_country_id.code == "CL":
            return "l10n_cl.report_invoice_document"
        return super()._get_name_invoice_report()

    @api.model
    def _pdf417_barcode(self, stored_stamp):
        """Encode the stored stamp for display in the original invoice report."""
        if not stored_stamp:
            return ""
        from pdf417gen import encode, render_image

        image = render_image(encode(stored_stamp.encode("latin-1"), columns=13, security_level=5))
        with BytesIO() as buffer:
            image.save(buffer, format="PNG")
            return base64.b64encode(buffer.getvalue()).decode("ascii")


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    account_id = fields.Many2one(ondelete="cascade")


class ReconcileModelLine(models.Model):
    _inherit = "account.reconcile.model.line"

    tax_ids = fields.Many2many(ondelete="restrict")


class Company(models.Model):
    _inherit = "res.company"

    l10n_cl_dte_resolution_date = fields.Date(**METADATA["l10n_cl_dte_resolution_date"])
    l10n_cl_dte_resolution_number = fields.Char(**METADATA["l10n_cl_dte_resolution_number"])
