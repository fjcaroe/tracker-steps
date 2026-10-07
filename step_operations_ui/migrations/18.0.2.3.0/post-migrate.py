"""T27 QA: marcar como transportistas de fletes a los contactos que ya se usan como tales."""


def migrate(cr, version):
    # All pre-migrations run before post-migrations; a later pre-migration
    # can already have renamed the tables when this historic step executes.
    from odoo.addons.step_operations_ui.migration_helpers import mark_freight_carriers
    mark_freight_carriers(cr)
