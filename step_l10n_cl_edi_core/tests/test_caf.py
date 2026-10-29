from odoo.tests import TransactionCase, tagged

from .caf_cases import CAFCaseMixin


@tagged('post_install', '-at_install')
class TestCAFCore(CAFCaseMixin, TransactionCase):
    # Odoo's loader enumerates methods in the concrete class __dict__.
    # Keep explicit forwarders so the shared crypto cases run in both engines.
    def test_real_rsa_verification_and_metadata(self):
        CAFCaseMixin.test_real_rsa_verification_and_metadata(self)

    def test_latin1_accent_entities_and_internal_spaces_are_signed(self):
        CAFCaseMixin.test_latin1_accent_entities_and_internal_spaces_are_signed(self)

    def test_complete_authorization_preserved_byte_for_byte(self):
        CAFCaseMixin.test_complete_authorization_preserved_byte_for_byte(self)

    def test_private_key_mismatch_and_invalid_key_rejected_without_echo(self):
        CAFCaseMixin.test_private_key_mismatch_and_invalid_key_rejected_without_echo(self)

    def test_missing_authority_never_trusts_caf_public_key(self):
        CAFCaseMixin.test_missing_authority_never_trusts_caf_public_key(self)

    def test_pinned_fingerprint_and_id_required(self):
        CAFCaseMixin.test_pinned_fingerprint_and_id_required(self)

    def test_changed_signed_values_fail(self):
        CAFCaseMixin.test_changed_signed_values_fail(self)

    def test_signature_bytes_and_algorithm_fail_closed(self):
        CAFCaseMixin.test_signature_bytes_and_algorithm_fail_closed(self)

    def test_dtd_entities_comments_and_processing_instructions_rejected(self):
        CAFCaseMixin.test_dtd_entities_comments_and_processing_instructions_rejected(self)

    def test_duplicate_wrapped_and_unknown_elements_rejected(self):
        CAFCaseMixin.test_duplicate_wrapped_and_unknown_elements_rejected(self)

    def test_foreign_and_prefixed_namespaces_rejected(self):
        CAFCaseMixin.test_foreign_and_prefixed_namespaces_rejected(self)

    def test_invalid_values_ranges_dates_and_issuer_rejected(self):
        CAFCaseMixin.test_invalid_values_ranges_dates_and_issuer_rejected(self)

    def test_size_type_encoding_and_unicode_bounds(self):
        CAFCaseMixin.test_size_type_encoding_and_unicode_bounds(self)

    def test_boundaries_and_date_check_without_counter_mutation(self):
        CAFCaseMixin.test_boundaries_and_date_check_without_counter_mutation(self)

    def test_context_and_unverified_receipts_rejected(self):
        CAFCaseMixin.test_context_and_unverified_receipts_rejected(self)

    def test_unique_selection_overlap_and_no_match(self):
        CAFCaseMixin.test_unique_selection_overlap_and_no_match(self)

    def test_selection_does_not_hide_invalid_signatures(self):
        CAFCaseMixin.test_selection_does_not_hide_invalid_signatures(self)

    def test_core_has_no_parallel_model_or_counter(self):
        module = self.env['ir.module.module'].search([('name', '=', 'step_l10n_cl_edi_core')])
        self.assertEqual(module.license, 'LGPL-3')
        data = self.env['ir.model.data'].search([('module', '=', 'step_l10n_cl_edi_core')])
        self.assertFalse(data.filtered(lambda row: row.model in
            ('ir.model', 'ir.model.fields', 'ir.sequence', 'ir.model.access', 'ir.rule')))
