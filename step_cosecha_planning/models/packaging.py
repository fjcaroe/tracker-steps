from odoo import fields, models


class ProductPackaging(models.Model):
    _inherit = 'product.packaging'

    step_packaging_group = fields.Selection([
        ('export', 'Exportación'), ('national', 'Nacional'), ('harvest', 'Cosecha'),
    ], string='Grupo embalaje', index=True,
        help='Clasificación del embalaje compartida entre Cosecha y los demás módulos. '
             'Los embalajes históricos conservan el grupo sin asignar hasta que se clasifiquen.')
