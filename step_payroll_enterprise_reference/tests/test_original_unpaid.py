from odoo.tests import TransactionCase, tagged
from odoo.addons.step_payroll_contracts.unpaid_testing import UnpaidRelationFixture


@tagged("post_install", "-at_install")
class OriginalUnpaidReferenceCase(UnpaidRelationFixture, TransactionCase):
    payroll_group = "hr_payroll.group_hr_payroll_manager"

    def test_real_unpaid_relation_metadata_inverse_and_raw_pairs(self):
        self.case_real_unpaid_relation_metadata_inverse_and_raw_pairs()

    def test_real_unpaid_relation_keeps_archived_original_pairs(self):
        self.case_real_unpaid_relation_keeps_archived_original_pairs()
