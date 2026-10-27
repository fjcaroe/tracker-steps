from odoo import api, SUPERUSER_ID
from odoo.addons.step_producers.migration import adopt_calendar_binding


def migrate(cr, version):
    if version:
        adopt_calendar_binding(api.Environment(cr, SUPERUSER_ID, {}), 'step_producer_estimate_report')
