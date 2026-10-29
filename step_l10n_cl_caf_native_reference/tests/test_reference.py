from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged
from odoo.addons.step_l10n_cl_caf_custody_core.tests.common import CAFCustodyAssertions


@tagged('post_install', '-at_install')
class TestNativeCAFCustody(CAFCustodyAssertions, TransactionCase):
    native_reference = True

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

    def test_new_fiscal_operations_stay_blocked(self):
        self.assert_no_fiscal_operation()

    def test_native_provider_methods_fields_and_ownership_remain_original(self):
        model = self.env.registry.models['l10n_cl.dte.caf']
        self.assertEqual(len(model._fields), 14)
        self.assertTrue(model._fields['caf_file'].attachment)
        for name in ('create', '_decode_caf', 'action_enable', 'action_spend'):
            method = getattr(model, name)
            self.assertTrue(method.__module__.startswith('odoo.addons.l10n_cl_edi.'), (name, method.__module__))
        self.assertEqual(self.env.ref('l10n_cl_edi.model_l10n_cl_dte_caf'),
                         self.env['ir.model']._get('l10n_cl.dte.caf'))
        self.assertFalse(self.env['ir.module.module'].search_count([
            ('name', '=', 'step_l10n_cl_caf_storage'), ('state', '=', 'installed')]))

    def test_new_upload_is_disabled_and_master_id_sequence_is_not_consumed(self):
        self.env.cr.execute('SELECT last_value,is_called FROM l10n_cl_dte_caf_id_seq')
        before = self.env.cr.fetchone()
        record = self.custody_record()
        with self.assertRaises(UserError):
            record.step_custody_upload()
        self.env.cr.execute('SELECT last_value,is_called FROM l10n_cl_dte_caf_id_seq')
        self.assertEqual(self.env.cr.fetchone(), before)
        self.assertEqual(record.id, -900001)
