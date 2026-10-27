def migrate(cr, version):
    from odoo import api,SUPERUSER_ID
    from odoo.addons.step_cosecha.hooks import post_init_hook
    post_init_hook(api.Environment(cr,SUPERUSER_ID,{}))
