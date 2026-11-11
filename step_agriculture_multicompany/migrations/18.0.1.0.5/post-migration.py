from odoo.addons.step_agriculture_multicompany.hooks import post_init_hook


def migrate(cr, version):
    from odoo import api, SUPERUSER_ID
    post_init_hook(api.Environment(cr, SUPERUSER_ID, {}))
