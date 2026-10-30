from odoo.tests import TransactionCase, tagged

from .ted_cases import TEDCaseMixin


@tagged('post_install', '-at_install')
class TestTEDCore(TEDCaseMixin, TransactionCase):
    # Concrete methods are required by Odoo's __dict__ test discovery.
    def test_real_frmt_signature_and_authority_are_separate(self):
        TEDCaseMixin.test_real_frmt_signature_and_authority_are_separate(self)

    def test_original_bytes_latin1_utf8_entities_spaces_and_safe_repr(self):
        TEDCaseMixin.test_original_bytes_latin1_utf8_entities_spaces_and_safe_repr(self)

    def test_signed_values_wrong_key_and_signature_algorithm_fail(self):
        TEDCaseMixin.test_signed_values_wrong_key_and_signature_algorithm_fail(self)

    def test_unsafe_xml_wrapping_duplicates_namespaces_and_size_fail_closed(self):
        TEDCaseMixin.test_unsafe_xml_wrapping_duplicates_namespaces_and_size_fail_closed(self)

    def test_caf_identity_folio_date_and_timestamp_boundaries(self):
        TEDCaseMixin.test_caf_identity_folio_date_and_timestamp_boundaries(self)

    def test_ordinary_liquidation_and_export_amounts_are_exact(self):
        TEDCaseMixin.test_ordinary_liquidation_and_export_amounts_are_exact(self)

    def test_stored_caf_is_bound_byte_for_byte_without_rewriting(self):
        TEDCaseMixin.test_stored_caf_is_bound_byte_for_byte_without_rewriting(self)

    def test_expected_context_compares_all_fields_and_rejects_float(self):
        TEDCaseMixin.test_expected_context_compares_all_fields_and_rejects_float(self)

    def test_forged_receipts_and_untrusted_authorities_do_not_enable_verification(self):
        TEDCaseMixin.test_forged_receipts_and_untrusted_authorities_do_not_enable_verification(self)

    def test_ted_adds_no_parallel_model_or_counter(self):
        data = self.env['ir.model.data'].search([('module', '=', 'step_l10n_cl_edi_core')])
        self.assertFalse(data.filtered(lambda row: row.model in
            ('ir.model', 'ir.model.fields', 'ir.sequence', 'ir.model.access', 'ir.rule')))
