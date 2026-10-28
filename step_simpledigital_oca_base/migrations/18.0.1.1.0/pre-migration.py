from odoo.addons.step_payroll_contracts.history import assert_history_snapshots


def migrate(cr,version):
    assert_history_snapshots(cr)
