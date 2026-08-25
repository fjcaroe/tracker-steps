from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    is_meal = fields.Boolean(
        string="Es colación",
        help="Habilita este producto para planificación, tarifas y tótems de colaciones.",
        index=True,
    )

