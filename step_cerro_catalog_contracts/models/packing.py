from odoo import fields, models


class StockPackageType(models.Model):
    _inherit = 'stock.package.type'

    base_weight = fields.Float(digits=(16, 2))
