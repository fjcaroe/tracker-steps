from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    dispatch_dte_provider = fields.Selection(
        [("third_party", "Tercero"), ("odoo", "Odoo")],
        string="Proveedor DTE para guías",
        default="third_party",
        required=True,
        help="Tercero registra un folio externo y genera un documento interno no tributario. "
             "Odoo queda reservado para la emisión DTE tipo 52 con CAF.",
    )


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    dispatch_dte_provider = fields.Selection(
        related="company_id.dispatch_dte_provider", readonly=False,
    )

