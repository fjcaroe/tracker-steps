from . import models

from odoo.addons.step_payroll_contracts.ytd import assert_ytd_snapshots


def pre_init_hook(env):
    assert_ytd_snapshots(env.cr)
