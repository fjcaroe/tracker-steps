"""Concrete Odoo discovery for the same offline upload-response cases."""
from odoo.tests import TransactionCase, tagged

from .upload_response_cases import UploadResponseCases


@tagged('post_install', '-at_install')
class TestUploadResponse(UploadResponseCases, TransactionCase):
    def test_public_success_is_receipt_not_dte_acceptance(self):
        UploadResponseCases.test_public_success_is_receipt_not_dte_acceptance(self)

    def test_public_failure_has_no_track_and_no_inferred_retry_policy(self):
        UploadResponseCases.test_public_failure_has_no_track_and_no_inferred_retry_policy(self)

    def test_public_schema_failure_retains_details_and_zero_padded_rut(self):
        UploadResponseCases.test_public_schema_failure_retains_details_and_zero_padded_rut(self)

    def test_published_fixture_provenance_and_hashes(self):
        UploadResponseCases.test_published_fixture_provenance_and_hashes(self)

    def test_both_encodings_accents_entities_and_original_bytes(self):
        UploadResponseCases.test_both_encodings_accents_entities_and_original_bytes(self)

    def test_rut_format_check_digit_and_zero_identity_rejected(self):
        UploadResponseCases.test_rut_format_check_digit_and_zero_identity_rejected(self)

    def test_track_numeric_positive_bound_and_literal_identity(self):
        UploadResponseCases.test_track_numeric_positive_bound_and_literal_identity(self)

    def test_status_and_track_consistency(self):
        UploadResponseCases.test_status_and_track_consistency(self)

    def test_status_format_and_unknown_failure_are_not_success(self):
        UploadResponseCases.test_status_format_and_unknown_failure_are_not_success(self)

    def test_duplicate_unknown_wrapped_and_mixed_root_fields_rejected(self):
        UploadResponseCases.test_duplicate_unknown_wrapped_and_mixed_root_fields_rejected(self)

    def test_namespace_and_root_attributes_are_not_alternate_formats(self):
        UploadResponseCases.test_namespace_and_root_attributes_are_not_alternate_formats(self)

    def test_dtd_external_and_internal_entities_are_never_expanded(self):
        UploadResponseCases.test_dtd_external_and_internal_entities_are_never_expanded(self)

    def test_comments_and_processing_instructions_are_rejected(self):
        UploadResponseCases.test_comments_and_processing_instructions_are_rejected(self)

    def test_scalar_nested_markup_attributes_and_detail_shape_rejected(self):
        UploadResponseCases.test_scalar_nested_markup_attributes_and_detail_shape_rejected(self)

    def test_xml_type_size_encoding_and_malformed_input_rejected(self):
        UploadResponseCases.test_xml_type_size_encoding_and_malformed_input_rejected(self)

    def test_local_timestamp_is_validated_without_timezone_assumption(self):
        UploadResponseCases.test_local_timestamp_is_validated_without_timezone_assumption(self)

    def test_context_admission_keeps_existing_identifier(self):
        UploadResponseCases.test_context_admission_keeps_existing_identifier(self)

    def test_context_mismatch_and_existing_track_cannot_be_overwritten(self):
        UploadResponseCases.test_context_mismatch_and_existing_track_cannot_be_overwritten(self)

    def test_forged_or_mutated_dataclass_cannot_bypass_reparse(self):
        UploadResponseCases.test_forged_or_mutated_dataclass_cannot_bypass_reparse(self)

    def test_representations_and_errors_never_echo_remote_content(self):
        UploadResponseCases.test_representations_and_errors_never_echo_remote_content(self)

    def test_no_network_or_state_changes_for_parsing_and_admission(self):
        UploadResponseCases.test_no_network_or_state_changes_for_parsing_and_admission(self)

    def test_error_detail_bounds_and_field_order(self):
        UploadResponseCases.test_error_detail_bounds_and_field_order(self)
