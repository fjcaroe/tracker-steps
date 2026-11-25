"""Required structure type for the original Cerro adoption profile."""
from odoo import fields, models


class PayrollStructure(models.Model):
    _inherit = 'hr.payroll.structure'

    type_id = fields.Many2one(required=True)
