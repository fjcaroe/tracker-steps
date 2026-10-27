def migrate(cr, version):
    from odoo import api, SUPERUSER_ID
    from odoo.addons.step_labor_operations_core.hooks import adopt_legacy_records
    adopt_legacy_records(api.Environment(cr,SUPERUSER_ID,{}))
