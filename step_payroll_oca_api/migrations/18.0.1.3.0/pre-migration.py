from odoo.addons.step_payroll_contracts.ytd import assert_ytd_snapshots


def migrate(cr,version):
    assert_ytd_snapshots(cr)
