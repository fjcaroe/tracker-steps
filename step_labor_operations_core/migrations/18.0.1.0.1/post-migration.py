def migrate(cr, version):
    from odoo import api, SUPERUSER_ID
    from odoo.addons.step_labor_operations_core.hooks import preserve_legacy_xmlids
    preserve_legacy_xmlids(api.Environment(cr,SUPERUSER_ID,{}))
