"""Retain original deletion policies through the real Community ORM.

Company-dependent account references are JSON properties, not SQL foreign keys.
Official Odoo's Many2one unlink policy checks every stored company slot; using
SET NULL there would silently erase an original payroll account mapping.
"""
from odoo import fields, models


class SalaryRule(models.Model):
    _inherit = "hr.salary.rule"

    account_debit = fields.Many2one(ondelete="restrict")
    account_credit = fields.Many2one(ondelete="restrict")


class StructureType(models.Model):
    _inherit = "hr.payroll.structure.type"

    default_struct_id = fields.Many2one(ondelete="set null")
