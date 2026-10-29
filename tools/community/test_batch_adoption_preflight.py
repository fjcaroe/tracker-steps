"""Preservation gates of the read-only preflight, independent of an Odoo engine."""
import copy
import unittest
import tempfile
from pathlib import Path

from batch_adoption_preflight import MODEL, assess, compare, identifier, licensed_candidate, validate_database, view_api


def contract():
    return {
        'models': [{'id': 5, 'model': MODEL}],
        'fields': [{'id': 10, 'model': 'account.payment', 'name': 'batch_payment_id',
                    'ttype': 'many2one', 'relation': MODEL, 'store': True},
                   {'id': 11, 'model': MODEL, 'name': 'state', 'ttype': 'selection', 'store': True},
                   {'id': 12, 'model': MODEL, 'name': 'amount', 'ttype': 'monetary', 'store': True}],
        'selections': [{'id': 20, 'field_id': 11, 'value': 'sent'}],
        'xmlids': [{'id': 30, 'module': 'account_batch_payment', 'name': 'model_account_batch_payment',
                    'model': 'ir.model', 'res_id': 5, 'noupdate': False}],
        'access': [{'id': 40, 'model_id': 5, 'perm_read': True, 'perm_write': False}],
        'rules': [{'id': 41, 'model_id': 5, 'domain_force': "[('company_id','in',company_ids)]"}],
        'rule_groups': [{'rule_group_id': 41, 'group_id': 8}],
        'modules': [{'name': 'account_batch_payment', 'state': 'installed', 'license': 'OEEL-1'},
                    {'name': 'account_accountant_batch_payment', 'state': 'installed', 'license': 'OEEL-1'}],
        'incoming_relations': [{'model': 'account.payment', 'name': 'batch_payment_id'}],
        'columns': [{'table_name': 'account_batch_payment', 'column_name': 'amount', 'data_type': 'numeric'}],
        'constraints': [{'table_name': 'account_payment', 'name': 'payment_batch_fkey', 'definition': 'FOREIGN KEY ...'}],
        'relation_owners': [{'id': 72, 'name': 'original_payment_rel', 'module': 9}],
        'views': [{'id': 50, 'model': MODEL, 'api': {'sha256': 'original'}}],
        'actions': [{'id': 60, 'res_model': MODEL}],
        'sequences': [{'id': 32, 'code': 'account.outbound.batch.payment', 'company_id': None}],
        'counters': {'ir_sequence_032_002': {'last_value': 1, 'is_called': False}},
        'stored_history': {'account_batch_payment': {'rows': 1, 'stored_rows_md5': 'original'}},
        'profile': {'batch_rows': 1, 'states': [{'state': 'draft', 'rows': 1}], 'linked_payments': 0},
    }


class BatchAdoptionPreflightCase(unittest.TestCase):
    def test_vendor_inspection_never_imports_candidate_or_copies_bodies(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / '__manifest__.py').write_text("{'version':'18.0.1.0.0','license':'AGPL-3','depends':['account']}")
            (root / 'model.py').write_text("raise RuntimeError('must never execute')\nclass Candidate:\n"
                " _name='account.payment.order'\n name=fields.Char()\n def confirm(self):\n  forbidden_body_marker()\n")
            result = licensed_candidate(root)
            self.assertEqual(result['models'][0]['_name'], 'account.payment.order')
            self.assertEqual(result['models'][0]['fields'], ['name'])
            self.assertNotIn('forbidden_body_marker', str(result))

    def test_enterprise_candidate_is_rejected_before_reading_model_bodies(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / '__manifest__.py').write_text("{'version':'18.0.1.0.0','license':'OEEL-1'}")
            (root / 'model.py').write_text('unparseable body must not be inspected')
            with self.assertRaises(ValueError):
                licensed_candidate(root)

    def test_production_names_and_shell_fragments_are_rejected(self):
        for name in ('CERRO_EL_PLOMO', 'SyS', 'karo_consultorias', 'LAB_TAREAS', 'postgres',
                     'COMMUNITY_X; DROP DATABASE x', 'COMMUNITY_'):
            with self.assertRaises(ValueError):
                validate_database(name)

    def test_existing_private_copy_prefixes_are_accepted(self):
        for name in ('COMMUNITY_PAYROLL_API_M', 'MANAGEMENT_QA_CERRO_X', 'MANAGEMENT_QA_SYS_STORAGE_B'):
            self.assertEqual(validate_database(name), name)

    def test_dynamic_table_names_cannot_inject_sql(self):
        self.assertEqual(identifier('account_payment'), '"account_payment"')
        for value in ('account.payment', 'a;select 1', 'public.account_payment', 'a"'):
            with self.assertRaises(ValueError):
                identifier(value)

    def test_view_probe_retains_api_and_hash_without_implementation_xml(self):
        xml = '<form><field name="payment_ids"/><button name="validate_batch_button" type="object"/></form>'
        info = view_api({'en_US': xml})
        self.assertEqual(info['fields'], ['payment_ids'])
        self.assertEqual(info['object_methods'], ['validate_batch_button'])
        self.assertEqual(len(info['sha256']), 64)
        self.assertNotIn(xml, str(info))
        self.assertNotIn('arch', info)

    def test_empty_draft_batch_never_certifies_a_conversion(self):
        proof = assess(contract())
        self.assertFalse(proof['conversion_ready'])
        self.assertFalse(proof['dependencies_may_change'])
        self.assertIn('NO_LINKED_BATCH_HISTORY_REFERENCE', proof['blockers'])
        self.assertIn('BATCH_ENGINE_STILL_ENTERPRISE', proof['blockers'])
        self.assertEqual(proof['stored_monetary_fields'], ['amount'])
        self.assertEqual(proof['state_keys'], ['sent'])

    def test_metadata_and_license_claim_alone_never_certify_a_provider(self):
        data = contract()
        data['profile']['linked_payments'] = 4
        data['modules'][0]['license'] = 'LGPL-3'
        proof = assess(data)
        self.assertFalse(proof['conversion_ready'])
        self.assertIn('FUNCTIONAL_COMMUNITY_PROVIDER_NOT_CERTIFIED', proof['blockers'])

    def test_missing_or_wrong_original_payment_link_is_a_blocker(self):
        data = contract()
        data['fields'][0]['ttype'] = 'char'
        self.assertIn('ORIGINAL_PAYMENT_BATCH_RELATION_ABSENT_OR_CHANGED', assess(data)['blockers'])

    def test_same_snapshot_passes_only_preservation_not_functional_conversion(self):
        proof = compare(contract(), contract())
        self.assertTrue(proof['original_contract_exact'])
        self.assertFalse(proof['functional_conversion_certified'])

    def test_xmlid_recreation_with_the_same_target_is_rejected(self):
        old = contract(); new = copy.deepcopy(old)
        new['xmlids'][0]['id'] = 31
        self.assertFalse(compare(old, new)['original_contract_exact'])

    def test_retargeting_original_model_or_field_is_rejected(self):
        for section, key, value in (('models', 'model', 'new.batch'), ('fields', 'relation', 'new.batch'),
                                    ('xmlids', 'res_id', 6), ('selections', 'value', 'uploaded')):
            old = contract(); new = copy.deepcopy(old)
            new[section][0][key] = value
            self.assertFalse(compare(old, new)['original_contract_exact'])

    def test_original_acl_and_rules_cannot_change(self):
        for section, key, value in (('access', 'perm_write', True), ('rules', 'domain_force', '[]')):
            old = contract(); new = copy.deepcopy(old)
            new[section][0][key] = value
            self.assertFalse(compare(old, new)['original_contract_exact'])

    def test_counter_or_stored_amount_fingerprint_change_is_rejected(self):
        old = contract(); new = copy.deepcopy(old)
        new['counters']['ir_sequence_032_002']['last_value'] = 2
        self.assertFalse(compare(old, new)['original_contract_exact'])
        new = copy.deepcopy(old)
        new['stored_history']['account_batch_payment']['stored_rows_md5'] = 'recomputed'
        self.assertFalse(compare(old, new)['original_contract_exact'])

    def test_original_fk_column_membership_and_view_cannot_disappear(self):
        for section in ('constraints', 'columns', 'rule_groups', 'views', 'relation_owners'):
            old = contract(); new = copy.deepcopy(old)
            new[section] = []
            self.assertFalse(compare(old, new)['original_contract_exact'])

    def test_only_scoped_false_to_true_owner_protection_is_allowed(self):
        old = contract(); new = copy.deepcopy(old)
        new['xmlids'][0]['noupdate'] = True
        self.assertTrue(compare(old, new)['original_contract_exact'])
        old['xmlids'][0]['module'] = 'base'
        new['xmlids'][0]['module'] = 'base'
        self.assertFalse(compare(old, new)['original_contract_exact'])


if __name__ == '__main__':
    unittest.main()
