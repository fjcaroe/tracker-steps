import base64

from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, tagged
from odoo.addons.step_l10n_cl_caf_custody_core.tests.common import CAFCustodyAssertions
from odoo.addons.step_l10n_cl_caf_custody_core.custody import CAFCustodyMixin
from ..hooks import _alias, check_provider_boundary, preserve_original_aliases


@tagged('post_install', '-at_install')
class TestCAFCustodyStorage(CAFCustodyAssertions, TransactionCase):
    # Concrete forwarders: Odoo does not select inherited mixin cases.
    def test_private_original_roundtrip(self):
        self.assert_private_roundtrip()

    def test_original_manager_roles(self):
        self.assert_original_roles()

    def test_company_and_unassigned_legacy_scope(self):
        self.assert_company_scope()

    def test_public_token_and_context_defaults_are_rejected(self):
        self.assert_no_public_or_token()

    def test_original_attachment_cannot_be_replaced_or_reassigned(self):
        self.assert_attachment_immutable()

    def test_cached_binary_download_rechecks_revoked_role(self):
        self.assert_cached_download_revoked()

    def test_fiscal_operations_stay_blocked(self):
        self.assert_no_fiscal_operation()

    def test_model_has_fourteen_fields_and_original_binary_storage(self):
        self.assertEqual(CAFCustodyMixin.__slots__, ())
        self.assertNotIn('__dict__', CAFCustodyMixin.__dict__)
        record = self.custody_record()
        self.assertEqual(len(record._fields), 14)
        self.assertTrue(record._fields['caf_file'].attachment)
        self.assertTrue(record._fields['caf_file'].store)
        self.assertFalse(record._fields['caf_file'].required)
        self.env.cr.execute("SELECT column_name FROM information_schema.columns WHERE table_schema='public' "
                            "AND table_name='l10n_cl_dte_caf'")
        self.assertNotIn('caf_file', [row[0] for row in self.env.cr.fetchall()])
        self.assertFalse(record.status)
        self.assertEqual(record.l10n_latam_document_type_id, self.document)
        self.assertIn(record, self.document.l10n_cl_dte_caf_ids)

    def test_upload_action_and_form_describe_actual_custody(self):
        action = self.manager_model().step_custody_upload('SYNTHETIC_NOT_SII_UPLOAD.xml',
            base64.b64encode(self.original), company_id=self.company.id, document_type_id=self.document.id)
        record = self.manager_model().browse(action['res_id'])
        self.assertTrue(record.caf_file)
        self.assertFalse(record.status)
        form = record.get_view(view_id=self.env.ref('step_l10n_cl_caf_storage.view_caf_custody_form').id,
                               view_type='form')['arch']
        self.assertIn('step_custody_download', form)
        self.assertIn('no habilita folios', form)
        for name in ('action_enable', 'action_spend'):
            with self.assertRaises(UserError):
                getattr(record, name)()

    def test_upload_cannot_spoof_masters_range_or_fiscal_status(self):
        original = dict(filename='SYNTHETIC_NOT_SII_REJECT.xml', caf_file=base64.b64encode(self.original),
                        company_id=self.company.id)
        for override in ({'company_id': self.other_company.id}, {'start_nb': 49}, {'final_nb': 102},
                         {'issued_date': '2026-09-01'}, {'status': 'in_use'}, {'status': 'spent'},
                         {'create_date': fields.Datetime.now()}):
            with self.subTest(keys=list(override)), self.assertRaises(UserError):
                self.manager_model().create(dict(original, **override))
        with self.assertRaises(AccessError):
            self.manager_model().with_user(self.employee).create(original)

    def test_invalid_xml_never_leaves_a_caf_or_attachment(self):
        before = self.env['l10n_cl.dte.caf'].search_count([])
        domain = [('res_model', '=', 'l10n_cl.dte.caf'), ('res_field', '=', 'caf_file')]
        attachments = self.env['ir.attachment'].search_count(domain)
        for raw in (b'not XML', b'<!DOCTYPE CAF [<!ENTITY x SYSTEM "file:///etc/passwd">]><CAF/>'):
            with self.assertRaises(UserError):
                self.manager_model().create({'filename': 'SYNTHETIC_INVALID.xml', 'caf_file': base64.b64encode(raw)})
        self.assertEqual(self.env['l10n_cl.dte.caf'].search_count([]), before)
        self.assertEqual(self.env['ir.attachment'].search_count(domain), attachments)

    def test_public_context_cannot_make_initial_binary_upload_public(self):
        count = self.env['l10n_cl.dte.caf'].search_count([])
        domain = [('res_model', '=', 'l10n_cl.dte.caf'), ('res_field', '=', 'caf_file')]
        attachments = self.env['ir.attachment'].search_count(domain)
        # Binary's native clean_context removes default_* when creating its
        # attachment. Require the actual result to stay private; no weakened
        # guard or artificial exception is needed for an already safe path.
        record = self.manager_model().with_context(default_public=True,
            default_access_token='SYNTHETIC_FORBIDDEN_TOKEN').create({
                'filename': 'SYNTHETIC_CONTEXT_PRIVATE.xml', 'caf_file': base64.b64encode(self.original)})
        attachment = self.attachment(record)
        self.assertFalse(attachment.public)
        self.assertFalse(attachment.access_token)
        self.assertEqual(self.env['l10n_cl.dte.caf'].search_count([]), count + 1)
        self.assertIn(attachment.id, self.env['ir.attachment'].search(domain).ids)
        self.assertEqual(self.env['ir.attachment'].search_count(domain), attachments + 1)

    def test_filename_unique_and_original_record_is_immutable(self):
        record = self.custody_record()
        with self.assertRaises(UserError):
            self.manager_model().create({'filename': record.filename, 'caf_file': base64.b64encode(self.original)})
        for values in ({'filename': 'renamed.xml'}, {'status': 'spent'}, {'company_id': self.other_company.id}):
            with self.assertRaises(UserError):
                record.write(values)
        with self.assertRaises(UserError):
            record.unlink()
        self.env.cr.execute("SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conrelid='l10n_cl_dte_caf'::regclass "
                            "AND contype='u'")
        self.assertIn(('UNIQUE (filename)',), self.env.cr.fetchall())

    def test_original_aliases_are_exact_and_conflicts_fail(self):
        preserve_original_aliases(self.env)
        for name in self.env['l10n_cl.dte.caf']._fields:
            alias = self.env.ref('l10n_cl_edi.field_l10n_cl_dte_caf__' + name)
            self.assertEqual((alias.model, alias.name), ('l10n_cl.dte.caf', name))
        self.assertEqual(self.env.ref('l10n_cl_edi.model_l10n_cl_dte_caf'),
                         self.env['ir.model']._get('l10n_cl.dte.caf'))
        with self.assertRaises(UserError):
            _alias(self.env, 'l10n_cl_edi', 'model_l10n_cl_dte_caf', 'ir.model', -1)
        self.assertEqual(self.env.ref('l10n_cl_edi.access_dte_caf_manager').group_id,
                         self.env.ref('account.group_account_manager'))
        self.assertEqual(self.env.ref('l10n_cl_edi_stock.access_dte_caf_manager').group_id,
                         self.env.ref('stock.group_stock_manager'))

    def test_duplicate_original_attachment_is_rejected_atomically(self):
        record = self.custody_record()
        before = self.attachment(record).ids
        with self.assertRaises(AccessError):
            self.env['ir.attachment'].with_context(allowed_company_ids=[self.company.id]).create({
                'name': 'SYNTHETIC_DUPLICATE.xml', 'res_model': record._name, 'res_id': record.id,
                'res_field': 'caf_file', 'datas': base64.b64encode(self.original)})
        self.assertEqual(self.attachment(record).ids, before)
