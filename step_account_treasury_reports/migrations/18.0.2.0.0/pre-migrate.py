from odoo import SUPERUSER_ID, api
from odoo.addons.step_account_treasury_reports.hooks import pre_init_reports


def migrate(cr, version):
    pre_init_reports(api.Environment(cr, SUPERUSER_ID, {}))
