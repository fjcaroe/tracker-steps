from odoo import api,SUPERUSER_ID
from odoo.addons.step_producer_daily_estimate import pre_init_hook


def migrate(cr,version):
    pre_init_hook(api.Environment(cr,SUPERUSER_ID,{}))
