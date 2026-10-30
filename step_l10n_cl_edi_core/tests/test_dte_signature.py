from odoo.tests import TransactionCase, tagged

from .dte_signature_cases import DTESignatureCaseMixin


@tagged('post_install', '-at_install')
class TestDTESignatureCore(DTESignatureCaseMixin, TransactionCase):
    # Odoo discovers concrete __dict__ methods, not inherited mixin methods.
    def test_real_signature_schema_context_and_authority_are_separate(self):
        DTESignatureCaseMixin.test_real_signature_schema_context_and_authority_are_separate(self)

    def test_encoding_entities_and_original_document_bytes_are_retained(self):
        DTESignatureCaseMixin.test_encoding_entities_and_original_document_bytes_are_retained(self)

    def test_signed_body_and_signature_tampering_are_rejected(self):
        DTESignatureCaseMixin.test_signed_body_and_signature_tampering_are_rejected(self)

    def test_wrapping_duplicate_ids_signatures_and_unsafe_xml_are_rejected(self):
        DTESignatureCaseMixin.test_wrapping_duplicate_ids_signatures_and_unsafe_xml_are_rejected(self)

    def test_external_references_and_algorithm_negotiation_are_rejected(self):
        DTESignatureCaseMixin.test_external_references_and_algorithm_negotiation_are_rejected(self)

    def test_every_expected_context_field_and_signing_instant_are_bound(self):
        DTESignatureCaseMixin.test_every_expected_context_field_and_signing_instant_are_bound(self)

    def test_pinned_certificate_key_usage_validity_and_key_match(self):
        DTESignatureCaseMixin.test_pinned_certificate_key_usage_validity_and_key_match(self)

    def test_no_resigning_or_construction_without_explicit_caf_anchor(self):
        DTESignatureCaseMixin.test_no_resigning_or_construction_without_explicit_caf_anchor(self)

    def test_official_schema_pins_and_no_external_resolution(self):
        DTESignatureCaseMixin.test_official_schema_pins_and_no_external_resolution(self)

    def test_canonicalization_known_vector_and_exact_decimal_context(self):
        DTESignatureCaseMixin.test_canonicalization_known_vector_and_exact_decimal_context(self)

    def test_document_liquidation_and_export_exact_amount_profiles(self):
        DTESignatureCaseMixin.test_document_liquidation_and_export_exact_amount_profiles(self)

    def test_explicit_new_unsigned_envelope_namespace_preparation(self):
        DTESignatureCaseMixin.test_explicit_new_unsigned_envelope_namespace_preparation(self)

    def test_envelope_preparation_never_rewrites_signed_or_mismatched_profiles(self):
        DTESignatureCaseMixin.test_envelope_preparation_never_rewrites_signed_or_mismatched_profiles(self)

    def test_dte_signature_adds_no_parallel_model_or_counter(self):
        data = self.env['ir.model.data'].search([('module', '=', 'step_l10n_cl_edi_core')])
        self.assertFalse(data.filtered(lambda row: row.model in
            ('ir.model', 'ir.model.fields', 'ir.sequence', 'ir.model.access', 'ir.rule')))
