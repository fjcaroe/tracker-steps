from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    packages = env['stock.quant.package'].search([])
    env.add_to_compute(packages._fields['kilos_total'], packages)
    packages._recompute_recordset()
