from odoo import fields, models


class Species(models.Model):
    _inherit = 'step.especie'

    tariff_code = fields.Char(string='Código arancelario')
