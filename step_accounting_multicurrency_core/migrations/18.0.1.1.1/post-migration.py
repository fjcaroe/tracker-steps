"""Retain original aliases using the native loader marker, not a flag write."""
from odoo import api, SUPERUSER_ID
from odoo.addons.step_accounting_multicurrency_core.hooks import preserve_legacy_xmlids


def migrate(cr, version):
    preserve_legacy_xmlids(api.Environment(cr, SUPERUSER_ID, {}))
