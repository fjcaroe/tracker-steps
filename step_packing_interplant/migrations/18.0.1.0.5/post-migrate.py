from odoo import SUPERUSER_ID, api
from odoo.addons.step_packing_interplant.hooks import configure_matrix_packing_sequences


def migrate(cr, version):
    if version:
        configure_matrix_packing_sequences(api.Environment(cr, SUPERUSER_ID, {}))
