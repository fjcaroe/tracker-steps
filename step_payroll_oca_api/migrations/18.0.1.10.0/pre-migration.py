from odoo.addons.step_payroll_contracts.ytd import assert_ytd_snapshots
from odoo.addons.step_payroll_oca_api.translation_storage import migrate_original_translation_storage


def migrate(cr, version):
    assert_ytd_snapshots(cr)
    migrate_original_translation_storage(cr)
