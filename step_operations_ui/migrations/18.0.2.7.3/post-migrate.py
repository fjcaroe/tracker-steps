from odoo.addons.step_operations_ui.migration_helpers import mark_freight_carriers


def migrate(cr, version):
    mark_freight_carriers(cr)
