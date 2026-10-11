from odoo import api, SUPERUSER_ID
from odoo.addons.step_export_client_revision.hooks import ensure_shipment_sequences


def migrate(cr, version):
    ensure_shipment_sequences(api.Environment(cr,SUPERUSER_ID,{}))
