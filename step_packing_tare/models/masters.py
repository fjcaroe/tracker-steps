from odoo import fields, models


class ProductPackaging(models.Model):
    _inherit = 'product.packaging'

    step_tare_weight = fields.Float(
        string='Tara de embalaje', digits=(16, 2),
        help='Peso en kg del embalaje vacío, sin incluir el producto ni el pallet.')


class StockPackageType(models.Model):
    _inherit = 'stock.package.type'

    # Native empty-package weight: preserve values and stock weight integration.
    base_weight = fields.Float(digits=(16, 2))
