from odoo.addons.step_payroll_contracts.history import assert_history_snapshots, assert_community_engine


def migrate(cr,version):
    assert_community_engine(cr)
    assert_history_snapshots(cr)
