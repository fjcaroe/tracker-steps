from base64 import b64encode
from io import BytesIO

from odoo import _, api, fields, models


STATUS = [
    ("not_sent", "Pending To Be Sent"),
    ("ask_for_status", "Ask For Status"),
    ("accepted", "Accepted"),
    ("objected", "Accepted With Objections"),
    ("rejected", "Rejected"),
    ("cancelled", "Cancelled"),
    ("manual", "Manual"),
]


REGIONAL_OFFICES = [
    ('ur_Anc', 'Ancud'),
    ('ur_Ang', 'Angol'),
    ('ur_Ant', 'Antofagasta'),
    ('ur_Ari', 'Arica y Parinacota'),
    ('ur_Ays', 'Aysén'),
    ('ur_Buin', 'Buin'),
    ('ur_Cal', 'Calama'),
    ('ur_Cas', 'Castro'),
    ('ur_Cau', 'Cauquenes'),
    ('ur_Cha', 'Chaitén'),
    ('ur_Chn', 'Chañaral'),
    ('ur_ChC', 'Chile Chico'),
    ('ur_Chi', 'Chillán'),
    ('ur_Coc', 'Cochrane'),
    ('ur_Cop', 'Concepción '),
    ('ur_Cos', 'Constitución'),
    ('ur_Coo', 'Copiapo'),
    ('ur_Coq', 'Coquimbo'),
    ('ur_Coy', 'Coyhaique'),
    ('ur_Cur', 'Curicó'),
    ('ur_Ill', 'Illapel'),
    ('ur_Iqu', 'Iquique'),
    ('ur_LaF', 'La Florida'),
    ('ur_LaL', 'La Ligua'),
    ('ur_LaS', 'La Serena'),
    ('ur_LaU', 'La Unión'),
    ('ur_Lan', 'Lanco'),
    ('ur_Leb', 'Lebu'),
    ('ur_Lin', 'Linares'),
    ('ur_Lod', 'Los Andes'),
    ('ur_Log', 'Los Ángeles'),
    ('ur_LosRios', 'Los Ríos'),
    ('ur_Nunoa', 'Ñuñoa'),
    ('ur_Maipu', 'Maipu'),
    ('ur_Melipilla', 'Melipilla'),
    ('ur_Oso', 'Osorno'),
    ('ur_Ova', 'Ovalle'),
    ('ur_Pan', 'Panguipulli'),
    ('ur_Par', 'Parral'),
    ('ur_Pic', 'Pichilemu'),
    ('ur_Por', 'Porvenir'),
    ('ur_PuM', 'Puerto Montt'),
    ('ur_PuN', 'Puerto Natales'),
    ('ur_PuV', 'Puerto Varas'),
    ('ur_PuA', 'Punta Arenas'),
    ('ur_Qui', 'Quillota'),
    ('ur_Ran', 'Rancagua'),
    ('ur_SaA', 'San Antonio'),
    ('ur_SanBernardo', 'San Bernardo'),
    ('ur_Sar', 'San Carlos'),
    ('ur_SaF', 'San Felipe'),
    ('ur_SaD', 'San Fernando'),
    ('ur_SaV', 'San Vicente de Tagua Tagua'),
    ('ur_SaZ', 'Santa Cruz'),
    ('ur_SaC', 'Santiago Centro'),
    ('ur_SaN', 'Santiago Norte'),
    ('ur_SaO', 'Santiago Oriente'),
    ('ur_SaP', 'Santiago Poniente'),
    ('ur_SaS', 'Santiago Sur'),
    ('ur_TaT', 'Tal-Tal'),
    ('ur_Tac', 'Talca'),
    ('ur_Tah', 'Talcahuano'),
    ('ur_Tem', 'Temuco'),
    ('ur_Toc', 'Tocopilla'),
    ('ur_Vld', 'Valdivia'),
    ('ur_Val', 'Vallenar'),
    ('ur_Vlp', 'Valparaíso'),
    ('ur_Vic', 'Victoria'),
    ('ur_ViA', 'Villa Alemana'),
    ('ur_ViR', 'Villarrica'),
    ('ur_ViM', 'Viña del Mar'),
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

    has_documents = fields.Boolean(string="Has Documents", compute="_compute_has_documents")

    def _compute_has_documents(self):
        moves = self._origin.filtered("id")
        moves.check_access("read")
        # The native invoice exposes the presence of linked documents. Opening them uses the library's own rules.
        groups = self.env["documents.document"].sudo()._read_group(
            [("res_model", "=", "account.move"), ("res_id", "in", moves.ids)], ["res_id"], []
        ) if moves else []
        linked = {resource_id for resource_id, in groups}
        for move in self:
            move.has_documents = move._origin.id in linked

    def action_view_documents_account_move(self):
        self.ensure_one()
        self.check_access("read")
        return {
            "name": _("Documents"), "type": "ir.actions.act_window", "res_model": "documents.document",
            "view_mode": "list,form", "domain": [("res_model", "=", self._name), ("res_id", "=", self.id)],
            "views": [(self.env.ref("step_document_library.library_list").id, "list"),
                      (self.env.ref("step_document_library.library_form").id, "form")],
        }

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
    l10n_cl_sii_regional_office = fields.Selection(REGIONAL_OFFICES, string="SII Regional Office")
