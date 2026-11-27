from odoo import SUPERUSER_ID, api
from odoo.addons.step_management_costs_agriculture.hooks import adopt_cost_center_bindings


def migrate(cr, version):
    adopt_cost_center_bindings(api.Environment(cr, SUPERUSER_ID, {}))
