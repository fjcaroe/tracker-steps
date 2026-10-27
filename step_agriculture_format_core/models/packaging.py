from odoo import fields, models

class StockPackageType(models.Model):
    _inherit = "stock.package.type"

    step_export_pallets_20 = fields.Float(string="Pallets por contenedor de 20 pies", digits=(12, 2))
    step_export_pallets_40 = fields.Float(string="Pallets por contenedor de 40 pies", digits=(12, 2))
