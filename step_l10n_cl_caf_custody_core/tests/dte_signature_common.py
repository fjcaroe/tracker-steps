"""Same real custody API on Community and the native reference provider."""
import base64
from dataclasses import replace
import hashlib
import json

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from odoo import Command
from odoo.exceptions import AccessError, UserError
from odoo.addons.step_l10n_cl_edi_core import caf, dte_signature
from odoo.addons.step_l10n_cl_edi_core.tests.dte_signature_cases import synthetic_certificate, synthetic_document

from .common import CAFCustodyAssertions


class DTESignatureCustodyAssertions(CAFCustodyAssertions):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.document_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        cls.certificate_pin = synthetic_certificate(cls.document_key)
        pem = cls.signer.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
        cls.anchor = caf.TrustAnchor(3, caf.public_key_fingerprint(cls.signer.public_key()), pem)
        unsigned, cls.dte_context = synthetic_document(cls.original, cls.issuer_key)
        cls.signed_dte = dte_signature.sign_dte(unsigned, cls.original, cls.certificate_pin,
            cls.dte_context, cls.document_key, caf_authorities={3: cls.anchor})

    def assert_dte_signature_check_is_readonly_and_has_no_fiscal_authority(self):
        record = self.custody_record()
        attachment = self.attachment(record)
        names = ['filename', 'company_id', 'l10n_latam_document_type_id', 'start_nb',
                 'final_nb', 'issued_date', 'status', 'write_uid', 'write_date']
        before = record.read(names)
        attachment_before = attachment.read(['checksum', 'file_size', 'public', 'write_date'])
        original_hash = hashlib.sha256(record._step_custody_original_bytes()).hexdigest()
        self.env.cr.execute('SELECT last_value,is_called FROM l10n_cl_dte_caf_id_seq')
        counter = self.env.cr.fetchone()
        for _ in range(2):
            result = record._step_custody_check_signed_dte(base64.b64encode(self.signed_dte),
                self.certificate_pin, self.dte_context)
            for name in ('dte_xml_signature_verified', 'sii_schema_verified', 'expected_context_matched'):
                self.assertTrue(result[name], name)
            for name in ('caf_authority_verified', 'signer_fiscal_authorization_verified',
                    'certificate_chain_verified', 'certificate_revocation_checked',
                    'folio_operations_enabled', 'sii_acceptance_certified', 'fiscal_emission_enabled'):
                self.assertFalse(result[name], name)
            self.assertNotIn('PRIVATE KEY', json.dumps(result))
            self.assertNotIn('RSASK', json.dumps(result))
        self.assertEqual(record.read(names), before)
        self.assertEqual(attachment.read(['checksum', 'file_size', 'public', 'write_date']), attachment_before)
        self.assertEqual(hashlib.sha256(record._step_custody_original_bytes()).hexdigest(), original_hash)
        self.env.cr.execute('SELECT last_value,is_called FROM l10n_cl_dte_caf_id_seq')
        self.assertEqual(self.env.cr.fetchone(), counter)
        with self.assertRaises(UserError):
            record.step_custody_reserve_folio()

    def assert_dte_signature_check_preserves_actor_company_and_unassigned_legacy_scope(self):
        record = self.custody_record()
        payload = base64.b64encode(self.signed_dte)
        for actor in (self.manager, self.stock_manager):
            scoped = record.with_user(actor).with_context(allowed_company_ids=[self.company.id])
            self.assertTrue(scoped._step_custody_check_signed_dte(payload,
                self.certificate_pin, self.dte_context)['dte_xml_signature_verified'])
        with self.assertRaises(AccessError):
            record.with_user(self.employee)._step_custody_check_signed_dte(payload,
                self.certificate_pin, self.dte_context)
        with self.assertRaises(AccessError):
            record.with_context(allowed_company_ids=[self.other_company.id])._step_custody_check_signed_dte(payload,
                self.certificate_pin, self.dte_context)
        self.env.cr.execute('UPDATE l10n_cl_dte_caf SET company_id=NULL WHERE id=%s', [record.id])
        record.invalidate_recordset(['company_id'])
        with self.assertRaises(AccessError):
            record._step_custody_check_signed_dte(payload, self.certificate_pin, self.dte_context)
        self.assertFalse(record.company_id)

    def assert_dte_signature_check_rechecks_cached_role_revocation(self):
        record = self.custody_record()
        args = (base64.b64encode(self.signed_dte), self.certificate_pin, self.dte_context)
        self.assertTrue(record._step_custody_check_signed_dte(*args)['dte_xml_signature_verified'])
        self.manager.write({'groups_id': [Command.unlink(self.env.ref('account.group_account_manager').id)]})
        with self.assertRaises(AccessError):
            record._step_custody_check_signed_dte(*args)

    def assert_bad_dte_context_and_pin_do_not_repair_caf_or_legacy_download(self):
        record = self.custody_record()
        original_hash = hashlib.sha256(record._step_custody_original_bytes()).hexdigest()
        for payload, pin, context in (
            (b'not base64!', self.certificate_pin, self.dte_context),
            (base64.b64encode(self.signed_dte.replace(b'SYNTHETIC 2', b'SYNTHETIC 3')), self.certificate_pin, self.dte_context),
            (base64.b64encode(self.signed_dte), replace(self.certificate_pin, fingerprint_sha256='0' * 64), self.dte_context),
            (base64.b64encode(self.signed_dte), self.certificate_pin, replace(self.dte_context, document_id='Other'))):
            with self.assertRaises(UserError) as caught:
                record._step_custody_check_signed_dte(payload, pin, context)
            self.assertNotIn('PRIVATE KEY', str(caught.exception))
        # There is no public signing/pin/authority endpoint; a trusted server
        # call cannot inject a CAF trust anchor into the custody boundary.
        with self.assertRaises(TypeError):
            record._step_custody_check_signed_dte(base64.b64encode(self.signed_dte),
                self.certificate_pin, self.dte_context, caf_authorities={3: self.anchor})
        self.assertEqual(hashlib.sha256(record._step_custody_original_bytes()).hexdigest(), original_hash)
        self.assertEqual(record.step_custody_download()['type'], 'ir.actions.act_url')

    def assert_dte_rejects_source_metadata_mismatch_without_repair(self):
        record = self.custody_record()
        original_hash = hashlib.sha256(record._step_custody_original_bytes()).hexdigest()
        self.env.cr.execute('UPDATE l10n_cl_dte_caf SET start_nb=49 WHERE id=%s', [record.id])
        record.invalidate_recordset(['start_nb'])
        with self.assertRaises(UserError):
            record._step_custody_check_signed_dte(base64.b64encode(self.signed_dte),
                self.certificate_pin, self.dte_context)
        self.assertEqual(record.start_nb, 49)
        self.assertEqual(hashlib.sha256(record._step_custody_original_bytes()).hexdigest(), original_hash)
        self.assertEqual(record.step_custody_download()['type'], 'ir.actions.act_url')
