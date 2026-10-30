"""TED custody exercises on the existing provider, real actors and attachments."""
import base64
import hashlib
import json

from odoo import Command
from odoo.exceptions import AccessError, UserError
from odoo.addons.step_l10n_cl_edi_core.tests.ted_cases import synthetic_ted

from .common import CAFCustodyAssertions


class TEDCustodyAssertions(CAFCustodyAssertions):
    def ted_fixture(self):
        return synthetic_ted(self.original, self.issuer_key)[0]

    def assert_ted_check_is_readonly_and_not_authority_or_folio_enablement(self):
        record = self.custody_record()
        attachment = self.attachment(record)
        names = ['filename', 'company_id', 'l10n_latam_document_type_id', 'start_nb',
                 'final_nb', 'issued_date', 'status', 'write_uid', 'write_date']
        before = record.read(names)
        prior_attachment = attachment.read(['checksum', 'file_size', 'public', 'write_date'])
        prior_sha = hashlib.sha256(record._step_custody_original_bytes()).hexdigest()
        self.env.cr.execute('SELECT last_value,is_called FROM l10n_cl_dte_caf_id_seq')
        prior_counter = self.env.cr.fetchone()
        for _ in range(2):
            result = record.step_custody_check_ted(base64.b64encode(self.ted_fixture()))
            self.assertTrue(result['ted_signature_verified'])
            self.assertFalse(result['caf_authority_verified'])
            self.assertFalse(result['folio_operations_enabled'])
            self.assertFalse(result['sii_acceptance_certified'])
            self.assertFalse(result['dte_xml_signature_verified'])
            self.assertFalse(result['expected_context_matched'])
            self.assertEqual((result['document_type'], result['folio'], result['total_text']), (33, 50, '1234'))
            self.assertNotIn('RSASK', json.dumps(result))
            self.assertNotIn('PRIVATE KEY', json.dumps(result))
        self.assertEqual(record.read(names), before)
        self.assertEqual(attachment.read(['checksum', 'file_size', 'public', 'write_date']), prior_attachment)
        self.assertEqual(hashlib.sha256(record._step_custody_original_bytes()).hexdigest(), prior_sha)
        self.env.cr.execute('SELECT last_value,is_called FROM l10n_cl_dte_caf_id_seq')
        self.assertEqual(self.env.cr.fetchone(), prior_counter)
        with self.assertRaises(UserError):
            record.step_custody_reserve_folio()

    def assert_ted_check_preserves_real_roles_and_company_scope(self):
        record = self.custody_record()
        payload = base64.b64encode(self.ted_fixture())
        for actor in (self.manager, self.stock_manager):
            result = record.with_user(actor).with_context(allowed_company_ids=[self.company.id]).step_custody_check_ted(payload)
            self.assertTrue(result['ted_signature_verified'])
        with self.assertRaises(AccessError):
            record.with_user(self.employee).step_custody_check_ted(payload)
        with self.assertRaises(AccessError):
            record.with_context(allowed_company_ids=[self.other_company.id]).step_custody_check_ted(payload)
        self.env.cr.execute('UPDATE l10n_cl_dte_caf SET company_id=NULL WHERE id=%s', [record.id])
        record.invalidate_recordset(['company_id'])
        with self.assertRaises(AccessError):
            record.step_custody_check_ted(payload)
        self.assertFalse(record.company_id)

    def assert_ted_check_rechecks_cached_role_revocation(self):
        record = self.custody_record()
        payload = base64.b64encode(self.ted_fixture())
        self.assertTrue(record.step_custody_check_ted(payload)['ted_signature_verified'])
        self.manager.write({'groups_id': [Command.unlink(self.env.ref('account.group_account_manager').id)]})
        with self.assertRaises(AccessError):
            record.step_custody_check_ted(payload)

    def assert_bad_ted_does_not_repair_caf_or_change_legacy_download(self):
        record = self.custody_record()
        prior = hashlib.sha256(record._step_custody_original_bytes()).hexdigest()
        raw = self.ted_fixture().replace(b'<MNT>1234</MNT>', b'<MNT>1235</MNT>')
        for payload in (base64.b64encode(raw), b'not-base64!', base64.b64encode(b'not XML')):
            with self.assertRaises(UserError) as caught:
                record.step_custody_check_ted(payload)
            self.assertNotIn('PRIVATE KEY', str(caught.exception))
        with self.assertRaises(TypeError):
            record.step_custody_check_ted(base64.b64encode(self.ted_fixture()), authorities={})
        self.assertEqual(hashlib.sha256(record._step_custody_original_bytes()).hexdigest(), prior)
        self.assertEqual(record.step_custody_download()['type'], 'ir.actions.act_url')

    def assert_ted_rejects_legacy_metadata_mismatch_without_repair_or_download_change(self):
        record = self.custody_record()
        prior = hashlib.sha256(record._step_custody_original_bytes()).hexdigest()
        # Explicit synthetic legacy inconsistency in the real private table.
        # The new validation rejects it; the existing custody read stays real.
        self.env.cr.execute('UPDATE l10n_cl_dte_caf SET start_nb=49 WHERE id=%s', [record.id])
        record.invalidate_recordset(['start_nb'])
        with self.assertRaises(UserError):
            record.step_custody_check_ted(base64.b64encode(self.ted_fixture()))
        self.assertEqual(record.start_nb, 49)
        self.assertEqual(hashlib.sha256(record._step_custody_original_bytes()).hexdigest(), prior)
        self.assertEqual(record.step_custody_download()['type'], 'ir.actions.act_url')
