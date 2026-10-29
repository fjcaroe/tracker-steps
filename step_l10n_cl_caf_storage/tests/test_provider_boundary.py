"""Early boundary guards with metadata-only cursor fixtures, no fake model."""
from unittest.mock import Mock

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged

from ..hooks import check_model_registration, reject_pending_native_provider


@tagged('post_install', '-at_install')
class TestCAFProviderBoundary(TransactionCase):
    def test_existing_actual_registry_class_cannot_be_overwritten(self):
        before = self.env.registry.models['l10n_cl.dte.caf']
        with self.assertRaises(UserError):
            check_model_registration(self.env.registry, self.env.cr)
        self.assertIs(self.env.registry.models['l10n_cl.dte.caf'], before)

    def test_same_graph_native_provider_is_rejected_before_registration(self):
        for name in ('l10n_cl_edi', 'step_l10n_cl_caf_native_reference'):
            cr = Mock(); cr.fetchone.return_value = (name,)
            with self.assertRaises(UserError):
                check_model_registration({}, cr)
            self.assertEqual(cr.execute.call_count, 1)
            statement, values = cr.execute.call_args.args
            self.assertIn("'to install'", statement)
            self.assertIn("'to upgrade'", statement)
            self.assertEqual(values, ['l10n_cl_edi', 'step_l10n_cl_caf_native_reference'])

    def test_cold_table_without_exact_community_owner_fails_closed(self):
        cr = Mock(); cr.fetchone.side_effect = [None, ('l10n_cl_dte_caf',)]
        cr.fetchall.return_value = []
        with self.assertRaises(UserError):
            check_model_registration({}, cr)
        self.assertEqual(cr.execute.call_count, 3)

    def test_clean_install_and_owned_upgrade_metadata_are_distinct(self):
        cr = Mock(); cr.fetchone.side_effect = [None, (None,)]
        check_model_registration({}, cr)
        self.assertEqual(cr.execute.call_count, 2)
        cr = Mock(); cr.fetchone.side_effect = [None, ('l10n_cl_dte_caf',)]
        cr.fetchall.return_value = [(987,)]
        check_model_registration({}, cr)
        self.assertEqual(cr.execute.call_count, 3)

    def test_guard_sql_contains_no_payload_reads_or_mutations(self):
        cr = Mock(); cr.fetchone.side_effect = [None, ('l10n_cl_dte_caf',)]
        cr.fetchall.return_value = []
        with self.assertRaises(UserError):
            check_model_registration({}, cr)
        statements = '\n'.join(call.args[0].lower() for call in cr.execute.call_args_list)
        for text in ('caf_file', 'db_datas', 'nextval(', 'setval(', 'update ', 'delete ', 'insert '):
            self.assertNotIn(text, statements)
