"""Original native actor baseline; metadata/ACLs are never replaced in tests."""
from odoo.tests import TransactionCase, tagged
from odoo.addons.step_payroll_contracts.original_security_actor_cases import OriginalSecurityActorCases


@tagged('post_install', '-at_install')
class OriginalSecurityNativeActorCase(OriginalSecurityActorCases, TransactionCase):
    NATIVE = True

    def test_original_user_crud_without_manager(self):
        self.case_officer_has_original_crud_or_generic_oca_readonly()

    def test_original_foreign_country_denied(self):
        self.case_foreign_country_is_blocked_including_warm_record()

    def test_original_field_permissions(self):
        self.case_original_field_access_does_not_assign_manager()

    def test_original_global_country_policy_has_no_invented_company_owner(self):
        self.case_global_originals_and_company_boundary_remain_distinct()
