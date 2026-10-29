from odoo.addons.step_payroll_contracts.ytd import assert_ytd_snapshots
from odoo.addons.step_payroll_oca_api.nullable_storage import admit_original_nullable_storage


def migrate(cr, version):
    assert_ytd_snapshots(cr)
    admit_original_nullable_storage(cr)
