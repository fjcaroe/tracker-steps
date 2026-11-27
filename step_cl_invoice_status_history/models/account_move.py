from odoo import fields, models


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
