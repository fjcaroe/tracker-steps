from odoo import api, fields, models
from odoo.exceptions import ValidationError


class ResCompany(models.Model):
    _inherit = "res.company"

    operational_currency_id = fields.Many2one(
        "res.currency",
        string="Moneda operacional",
        help=(
            "Segunda moneda en la que se conserva cada transacción contable "
            "al momento de registrarla."
        ),
    )

    @api.constrains("currency_id", "operational_currency_id")
    def _check_operational_currency(self):
        for company in self:
            if company.operational_currency_id == company.currency_id:
                raise ValidationError(
                    "La moneda operacional debe ser distinta de la moneda principal."
                )


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    operational_currency_id = fields.Many2one(
        related="company_id.operational_currency_id",
        readonly=False,
        string="Moneda operacional",
    )
