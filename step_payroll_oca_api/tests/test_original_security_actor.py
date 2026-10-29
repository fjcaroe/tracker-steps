"""A generic OCA installation keeps its real user rights pending adoption."""
from odoo.tests import TransactionCase, tagged
from odoo.addons.step_payroll_contracts.original_security_actor_cases import OriginalSecurityActorCases


@tagged('post_install', '-at_install')
class OriginalSecurityCommunityActorCase(OriginalSecurityActorCases, TransactionCase):
    NATIVE = False

    def test_generic_oca_user_does_not_gain_native_crud(self):
        self.case_officer_has_original_crud_or_generic_oca_readonly()

    def test_generic_oca_country_policy_denies_foreign_country(self):
        self.case_foreign_country_is_blocked_including_warm_record()

    def test_generic_oca_field_permissions(self):
        self.case_original_field_access_does_not_assign_manager()

    def test_generic_oca_global_and_company_rules(self):
        self.case_global_originals_and_company_boundary_remain_distinct()
