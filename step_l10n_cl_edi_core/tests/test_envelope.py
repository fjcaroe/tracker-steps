from odoo.tests import TransactionCase, tagged

from .envelope_cases import EnvelopeCaseMixin


@tagged('post_install', '-at_install')
class TestEnvioDTECore(EnvelopeCaseMixin, TransactionCase):
    def test_official_header_xsd_set_signature_and_every_embedded_signature(self):
        EnvelopeCaseMixin.test_official_header_xsd_set_signature_and_every_embedded_signature(self)

    def test_latin1_utf8_and_signed_input_fragments_are_byte_exact(self):
        EnvelopeCaseMixin.test_latin1_utf8_and_signed_input_fragments_are_byte_exact(self)

    def test_counts_caratula_fields_and_explicit_context_are_bound(self):
        EnvelopeCaseMixin.test_counts_caratula_fields_and_explicit_context_are_bound(self)

    def test_valid_foreign_issuer_and_counterparty_documents_cannot_be_mixed(self):
        EnvelopeCaseMixin.test_valid_foreign_issuer_and_counterparty_documents_cannot_be_mixed(self)

    def test_duplicate_ids_and_duplicate_fiscal_identities_are_rejected(self):
        EnvelopeCaseMixin.test_duplicate_ids_and_duplicate_fiscal_identities_are_rejected(self)

    def test_wrapping_external_references_header_and_algorithm_tampering_fail(self):
        EnvelopeCaseMixin.test_wrapping_external_references_header_and_algorithm_tampering_fail(self)

    def test_tampered_or_reordered_documents_never_return_a_usable_envelope(self):
        EnvelopeCaseMixin.test_tampered_or_reordered_documents_never_return_a_usable_envelope(self)

    def test_resolution_times_recipient_policy_and_certificate_claims_are_explicit(self):
        EnvelopeCaseMixin.test_resolution_times_recipient_policy_and_certificate_claims_are_explicit(self)

    def test_resource_encoding_and_explicit_authority_guards_fail_closed(self):
        EnvelopeCaseMixin.test_resource_encoding_and_explicit_authority_guards_fail_closed(self)

    def test_standalone_signed_documents_are_not_rewritten_for_inherited_namespace(self):
        EnvelopeCaseMixin.test_standalone_signed_documents_are_not_rewritten_for_inherited_namespace(self)

    def test_envelope_adds_no_parallel_model_counter_or_acl(self):
        data = self.env['ir.model.data'].search([('module', '=', 'step_l10n_cl_edi_core')])
        self.assertFalse(data.filtered(lambda row: row.model in
            ('ir.model', 'ir.model.fields', 'ir.sequence', 'ir.model.access', 'ir.rule')))
