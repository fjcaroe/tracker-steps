"""Salary category declaration installed only by the original Cerro profile."""
from odoo import fields, models


class SalaryRuleCategory(models.Model):
    _inherit = 'hr.salary.rule.category'

    code = fields.Char(required=True)
