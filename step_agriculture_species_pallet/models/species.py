from odoo import fields, models


class Species(models.Model):
    _inherit = 'step.especie'
    sag_code = fields.Char(string='Código SAG')
    base_boxes_per_pallet = fields.Float(string='Caja Base x pallet', digits=(16, 2))
    _sql_constraints = [('base_boxes_per_pallet_nonnegative', 'CHECK(base_boxes_per_pallet >= 0)', 'Caja Base x pallet no puede ser negativa.')]
