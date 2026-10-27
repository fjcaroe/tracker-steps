from odoo import api, SUPERUSER_ID
from odoo.addons.step_agriculture_core.hooks import adopt_legacy_records


def migrate(cr, version):
    if version:
        adopt_legacy_records(api.Environment(cr, SUPERUSER_ID, {}))
