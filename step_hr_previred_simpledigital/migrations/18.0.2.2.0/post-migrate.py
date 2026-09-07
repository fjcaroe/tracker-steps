"""Excluye las cotizaciones patronales del trabajador PreviRed tipo 3."""

from odoo import SUPERUSER_ID, api

from odoo.addons.step_hr_previred_simpledigital import hooks


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    hooks.apply_salary_rule_overrides(env)
