"""Refuse an implicit historical Float8 cast before any ORM schema change."""
from odoo.addons.step_payroll_oca_api.input_storage import admit_original_input_storage


def migrate(cr, version):
    admit_original_input_storage(cr)
