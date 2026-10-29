"""Retain actual Community models and move_id delegated fields in both APIs."""
from odoo import api, SUPERUSER_ID
from odoo.addons.step_accounting_multicurrency_core.hooks import preserve_legacy_xmlids


def migrate(cr, version):
    preserve_legacy_xmlids(api.Environment(cr, SUPERUSER_ID, {}))
