from odoo import SUPERUSER_ID, api
from odoo.addons.step_packing_tag_company.hooks import post_init_hook


def migrate(cr, version):
    if version:
        post_init_hook(api.Environment(cr, SUPERUSER_ID, {}))
