from odoo import SUPERUSER_ID, api
from odoo.addons.step_packing_interplant.hooks import configure_shipment_dispatch_types


def migrate(cr, version):
    if version:
        configure_shipment_dispatch_types(api.Environment(cr, SUPERUSER_ID, {}))
