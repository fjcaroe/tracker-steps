"""Adopt model and delegated-field XMLIDs before the report bridge upgrades."""
from odoo import api, SUPERUSER_ID
from odoo.addons.step_accounting_multicurrency_core.hooks import adopt_legacy_records


def migrate(cr, version):
    adopt_legacy_records(api.Environment(cr, SUPERUSER_ID, {}))
