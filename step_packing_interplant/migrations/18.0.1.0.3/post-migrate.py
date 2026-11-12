from odoo import SUPERUSER_ID, api
from odoo.addons.step_packing_interplant.hooks import preserve_legacy_tag_companies


def migrate(cr, version):
    if version:
        preserve_legacy_tag_companies(api.Environment(cr, SUPERUSER_ID, {}))
