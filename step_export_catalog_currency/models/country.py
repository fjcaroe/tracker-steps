from odoo import fields, models


class Country(models.Model):
    _inherit = 'res.country'

    fruit_market_id = fields.Many2one('step.fruit.market', string='Mercado', ondelete='restrict')
