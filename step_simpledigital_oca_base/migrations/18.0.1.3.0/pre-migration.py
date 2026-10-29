from odoo.addons.step_payroll_contracts.history import assert_history_snapshots, assert_community_engine
from odoo.addons.step_simpledigital_oca_base.analytic_storage import migrate_original_analytic_storage


def migrate(cr, version):
    assert_community_engine(cr)
    assert_history_snapshots(cr)
    migrate_original_analytic_storage(cr)
