from odoo.tests import TransactionCase, tagged
from odoo.addons.step_payroll_contracts.original_type_relation_cases import OriginalTypeRelationCases


@tagged("post_install", "-at_install")
class OriginalTypeRelationsReference(OriginalTypeRelationCases, TransactionCase):
    NATIVE = True

    def test_type_inverse_is_original(self):
        self.case_type_inverse_is_the_original_fk_without_a_shadow_relation()

    def test_type_inverse_write(self):
        self.case_type_inverse_write_moves_the_real_fk_and_related_schedule()

    def test_related_schedule(self):
        self.case_schedule_is_readonly_related_and_changes_without_storing_a_new_value()

    def test_original_visible_count(self):
        self.case_count_uses_the_current_visible_original_inverse()
