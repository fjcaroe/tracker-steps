from odoo.tests import TransactionCase, tagged
from odoo.addons.step_l10n_cl_caf_custody_core.tests.ted_common import TEDCustodyAssertions


@tagged('post_install', '-at_install')
class TestTEDNativeCAFCustody(TEDCustodyAssertions, TransactionCase):
    native_reference = True

    def test_ted_check_is_readonly_and_not_authority_or_folio_enablement(self):
        self.assert_ted_check_is_readonly_and_not_authority_or_folio_enablement()

    def test_ted_check_preserves_real_roles_and_company_scope(self):
        self.assert_ted_check_preserves_real_roles_and_company_scope()

    def test_ted_check_rechecks_cached_role_revocation(self):
        self.assert_ted_check_rechecks_cached_role_revocation()

    def test_bad_ted_does_not_repair_caf_or_change_legacy_download(self):
        self.assert_bad_ted_does_not_repair_caf_or_change_legacy_download()

    def test_ted_rejects_legacy_metadata_mismatch_without_repair_or_download_change(self):
        self.assert_ted_rejects_legacy_metadata_mismatch_without_repair_or_download_change()
