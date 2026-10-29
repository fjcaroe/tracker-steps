from . import models

from odoo.addons.step_payroll_contracts.ytd import assert_ytd_snapshots
from .translation_storage import migrate_original_translation_storage
from .nullable_storage import admit_original_nullable_storage


def pre_init_hook(env):
    assert_ytd_snapshots(env.cr)
    admit_original_nullable_storage(env.cr)
    migrate_original_translation_storage(env.cr)
