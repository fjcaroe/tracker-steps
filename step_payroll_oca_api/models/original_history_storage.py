"""Retain original scalar/nullable storage without rewriting historical rows.

The pinned free-engine overlay must use the same declarations before its first
initialization. These adapter fields keep that contract through later upgrades;
they do not convert JSONB, select a language, infer attendance or compute pay.
"""
from odoo import fields, models


class Contract(models.Model):
    _inherit = 'hr.contract'

    resource_calendar_id = fields.Many2one(required=False, ondelete='set null')


class WorkedDays(models.Model):
    _inherit = 'hr.payslip.worked_days'

    name = fields.Char(required=False)


class PayslipLine(models.Model):
    _inherit = 'hr.payslip.line'

    # A stored payslip line is an original literal, independently of the
    # translated rule master inherited by the actual OCA model.
    name = fields.Char(required=True, translate=False)
