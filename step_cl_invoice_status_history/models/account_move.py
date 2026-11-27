from base64 import b64encode
from io import BytesIO

from odoo import api, fields, models


STATUS = [
    ("not_sent", "Pending To Be Sent"),
    ("ask_for_status", "Ask For Status"),
    ("accepted", "Accepted"),
    ("objected", "Accepted With Objections"),
    ("rejected", "Rejected"),
    ("cancelled", "Cancelled"),
    ("manual", "Manual"),
]


class InvoiceReference(models.Model):
    _name = "l10n_cl.account.invoice.reference"
    _description = "Referencia de un documento tributario chileno"
    _rec_name = "origin_doc_number"
    _auto = False
    _log_access = True

    origin_doc_number = fields.Char(string="Origin Document Number", required=True)
    date = fields.Date(string="Document Date", required=True)
    move_id = fields.Many2one("account.move", string="Originating Document", index=True, ondelete="cascade")
    l10n_cl_reference_doc_type_id = fields.Many2one("l10n_latam.document.type", string="SII Doc Type Selector",
                                                    ondelete="set null")
    l10n_cl_reference_doc_internal_type = fields.Selection(related="l10n_cl_reference_doc_type_id.internal_type")
    reference_doc_code = fields.Selection([("1", "1. Cancels Referenced Document"),
                                           ("2", "2. Corrects Referenced Document Text"),
                                           ("3", "3. Corrects Referenced Document Amount")],
                                          string="SII Reference Code")
    reason = fields.Char(string="Reason")


class AccountMove(models.Model):
    _inherit = "account.move"

    l10n_cl_dte_status = fields.Selection(STATUS, string="SII DTE status", copy=False, tracking=True)
    l10n_cl_dte_file = fields.Many2one("ir.attachment", string="DTE file", copy=False,
                                       ondelete="set null", groups="base.group_system")
    l10n_cl_sii_barcode = fields.Char(string="SII Barcode", readonly=True, copy=False)
    l10n_cl_reference_ids = fields.One2many("l10n_cl.account.invoice.reference", "move_id",
                                           string="Reference Records", copy=False)

    signing_user = fields.Many2one("res.users", string="Signer", readonly=True, copy=False, ondelete="set null")
    show_signature_area = fields.Boolean(string="Show Signature Area", compute="_compute_print_signature")
    signature = fields.Binary(string="Signature", compute="_compute_print_signature")

    @api.depends("company_id.sign_invoice", "move_type", "state", "signing_user")
    def _compute_print_signature(self):
        for move in self:
            visible = move.company_id.sign_invoice and move.state == "posted" and move.move_type in ("out_invoice", "out_refund")
            move.show_signature_area = visible
            # Historical Steps did not install Sign. An optional signature provider can supply an existing image.
            signer = move.signing_user
            move.signature = signer.sign_signature if visible and signer and "sign_signature" in signer._fields else False

    @api.model
    def _pdf417_barcode(self, stored_stamp):
        """Render the stamp already present on the historical invoice."""
        if not stored_stamp:
            return ""
        from pdf417gen import encode, render_image

        with BytesIO() as png:
            render_image(encode(stored_stamp.encode("latin-1"), columns=13, security_level=5)).save(png, format="PNG")
            return b64encode(png.getvalue()).decode("ascii")


class Company(models.Model):
    _inherit = "res.company"

    sign_invoice = fields.Boolean(string="Display signing field on invoices")
    signing_user = fields.Many2one("res.users", string="Signing User", ondelete="set null")
    l10n_cl_dte_resolution_date = fields.Date(string="SII Exempt Resolution Date")
    l10n_cl_dte_resolution_number = fields.Char(string="SII Exempt Resolution Number")
