from odoo.addons.step_hr.migration_guard import require_payroll_bridge


def migrate(cr, version):
    require_payroll_bridge(cr)
