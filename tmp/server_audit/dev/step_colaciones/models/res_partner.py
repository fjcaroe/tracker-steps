from odoo import fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    is_meal_supplier = fields.Boolean(
        string="Es proveedor de colaciones",
        help="Habilita este contacto como proveedor en la aplicación Colaciones.",
        index=True,
    )

