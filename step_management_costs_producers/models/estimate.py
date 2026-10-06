"""Support both deployed producer releases without promoting unrelated features."""
from odoo import fields, models


class ProducerEstimate(models.Model):
    _inherit = 'step.export.estimate'

    cost_center_id = fields.Many2one('account.analytic.account', string='Centro de costos', check_company=True)
