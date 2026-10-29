from . import models

from odoo.addons.step_payroll_contracts.ytd import assert_ytd_snapshots
from .translation_storage import migrate_original_translation_storage


def pre_init_hook(env):
    assert_ytd_snapshots(env.cr)
    migrate_original_translation_storage(env.cr)
