"""Retain the existing original flags and establish the actual core owner."""
from odoo import api, SUPERUSER_ID
from odoo.addons.step_bank_export_core.hooks import adopt_legacy_fields


def migrate(cr, version):
    adopt_legacy_fields(api.Environment(cr, SUPERUSER_ID, {}))
