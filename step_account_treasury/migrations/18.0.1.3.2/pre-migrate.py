from odoo import SUPERUSER_ID, api
from odoo.addons.step_account_treasury.report_ownership import preserve_menus


def migrate(cr, version):
    preserve_menus(api.Environment(cr, SUPERUSER_ID, {}), require_bridge=True)
