"""Mark the exact bank aliases through the loader without changing noupdate."""
from odoo import api, SUPERUSER_ID
from odoo.addons.step_bank_export_core.hooks import preserve_legacy_xmlids


def migrate(cr, version):
    preserve_legacy_xmlids(api.Environment(cr, SUPERUSER_ID, {}))
