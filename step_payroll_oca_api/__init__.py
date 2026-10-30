from . import models

from odoo.addons.step_payroll_contracts.ytd import assert_ytd_snapshots
from .translation_storage import migrate_original_translation_storage
from .nullable_storage import admit_original_nullable_storage
from .input_storage import admit_original_input_storage


def pre_init_hook(env):
    admit_original_input_storage(env.cr)
    assert_ytd_snapshots(env.cr)
    admit_original_nullable_storage(env.cr)
    # Admit scalar input names before ORM can discard JSON language members.
    # The same entry point preserves the independent translated rule notes.
    migrate_original_translation_storage(env.cr)
