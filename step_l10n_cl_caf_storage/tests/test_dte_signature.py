from odoo.tests import TransactionCase, tagged
from odoo.addons.step_l10n_cl_caf_custody_core.tests.dte_signature_common import DTESignatureCustodyAssertions


@tagged('post_install', '-at_install')
class TestDTESignatureCustodyStorage(DTESignatureCustodyAssertions, TransactionCase):
    def test_dte_signature_check_is_readonly_and_has_no_fiscal_authority(self):
        self.assert_dte_signature_check_is_readonly_and_has_no_fiscal_authority()

    def test_dte_signature_check_preserves_actor_company_and_unassigned_legacy_scope(self):
        self.assert_dte_signature_check_preserves_actor_company_and_unassigned_legacy_scope()

    def test_dte_signature_check_rechecks_cached_role_revocation(self):
        self.assert_dte_signature_check_rechecks_cached_role_revocation()

    def test_bad_dte_context_and_pin_do_not_repair_caf_or_legacy_download(self):
        self.assert_bad_dte_context_and_pin_do_not_repair_caf_or_legacy_download()

    def test_dte_rejects_source_metadata_mismatch_without_repair(self):
        self.assert_dte_rejects_source_metadata_mismatch_without_repair()
