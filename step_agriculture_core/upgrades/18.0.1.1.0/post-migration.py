from odoo import api, SUPERUSER_ID
from odoo.addons.step_agriculture_core.hooks import preserve_legacy_xmlids


def migrate(cr, version):
    if version:
        preserve_legacy_xmlids(api.Environment(cr, SUPERUSER_ID, {}))
