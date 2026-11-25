"""Required primary rule ownership in the private Cerro adoption profile."""
from odoo import fields, models


class SalaryRule(models.Model):
    _inherit = 'hr.salary.rule'

    struct_id = fields.Many2one(required=True)


class PayslipLine(models.Model):
    _inherit = 'hr.payslip.line'

    # OCA inherits rule fields on lines. Preserve the optional column there.
    struct_id = fields.Many2one(required=False)
