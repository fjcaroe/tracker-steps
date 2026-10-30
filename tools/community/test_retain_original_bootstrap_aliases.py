import copy
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import retain_original_bootstrap_aliases as retain
from test_plan_original_payroll_bootstrap import fixture


class Cursor:
    dbname = 'MANAGEMENT_QA_CERRO_PAYROLL_API_ADOPTION_SANDBOX_TEST'

    def __init__(self, responses):
        self.responses = list(responses)
        self.statements = []

    def execute(self, sql, params=None):
        if not sql.startswith('SELECT '):
            raise AssertionError('A retention helper must never write SQL')
        self.statements.append((sql, params))

    def fetchall(self):
        return self.responses.pop(0)


class OriginalAliasRetentionCase(unittest.TestCase):
    def response(self, contract):
        responses = [[]]
        for item in contract:
            responses.extend([
                [tuple(item['alias'][name] for name in ('id', 'module', 'name', 'model', 'res_id', 'noupdate'))],
                [tuple(item['model'][name] for name in ('id', 'model', 'state'))],
                sorted((row['id'], row['model'], row['name'], row['state']) for row in item['fields']),
                [(True, 'same-pg-md5', 'same-pg-md5')],
            ])
        return responses

    def invoke(self, capsule, identity, responses, *, database=None):
        cr = Cursor(responses)
        if database: cr.dbname = database
        env = SimpleNamespace(cr=cr, registry=SimpleNamespace(loaded_xmlids={'base.existing'}))
        with patch.object(retain, '_read_sealed', side_effect=[capsule, identity]), \
                patch.object(retain, '_require_oca_models'):
            result = retain.retain_original_aliases(env, capsule_path='/private/capsule',
                capsule_sha256=retain.CAPSULE_SHA256, original_identity_path='/private/identity',
                original_identity_sha256='sealed-identity')
        return result, env

    def test_only_two_original_false_aliases_reach_loaded_set_after_both_pg_checks(self):
        capsule, identity, _ = fixture()
        contract = retain._contract(capsule, identity)
        result, env = self.invoke(capsule, identity, self.response(contract))
        self.assertEqual(env.registry.loaded_xmlids, {'base.existing',
            'l10n_cl_simpledigital_payroll.structure_type_chile',
            'l10n_cl_simpledigital_payroll.structure_chile'})
        self.assertTrue(result['exact_two_aliases_retained'])
        self.assertTrue(all(row['noupdate'] is False and row['noupdate_exact'] is True for row in result['aliases']))
        self.assertFalse(result['sql_writes'])
        self.assertEqual(len(env.cr.statements), 9)
        self.assertTrue(all(sql.startswith('SELECT ') for sql, _ in env.cr.statements))

    def test_no_partial_retention_on_late_original_values_failure(self):
        capsule, identity, _ = fixture()
        contract = retain._contract(capsule, identity)
        responses = self.response(contract)
        responses[-1] = [(False, 'current', 'original')]
        cr = Cursor(responses)
        env = SimpleNamespace(cr=cr, registry=SimpleNamespace(loaded_xmlids={'base.existing'}))
        with patch.object(retain, '_read_sealed', side_effect=[capsule, identity]), \
                patch.object(retain, '_require_oca_models'), \
                self.assertRaisesRegex(ValueError, 'retained-original-master-values-or-null-drift'):
            retain.retain_original_aliases(env, capsule_path='/private/capsule', capsule_sha256=retain.CAPSULE_SHA256,
                original_identity_path='/private/identity', original_identity_sha256='hash')
        self.assertEqual(env.registry.loaded_xmlids, {'base.existing'})

    def test_alias_field_identity_or_uninstall_state_failure_has_no_loaded_set_mutation(self):
        capsule, identity, _ = fixture()
        contract = retain._contract(capsule, identity)
        for index, wrong in [(0, [('native',)]), (1, []), (3, [])]:
            with self.subTest(index=index):
                responses = self.response(contract)
                responses[index] = wrong
                with self.assertRaises(ValueError):
                    self.invoke(capsule, identity, responses)

    def test_capsule_cannot_retain_different_ids_flags_or_names(self):
        for field, value in [('id', 90000), ('res_id', 3), ('noupdate', True), ('name', 'other')]:
            capsule, identity, _ = fixture()
            row = next(row for row in capsule['xmlids'] if row['id'] == 58549)
            identity_row = next(row for row in identity['original_xmlids'] if row['id'] == 58549)
            row[field] = identity_row[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                retain._contract(capsule, identity)

    def test_nonprivate_database_and_false_registry_provider_fail_closed(self):
        capsule, identity, _ = fixture()
        with self.assertRaisesRegex(ValueError, 'private-native-anchor-required'):
            self.invoke(capsule, identity, [], database='CERROELPLOMO')
        class Registry(dict):
            pass
        registry = Registry()
        env = SimpleNamespace(registry=registry)
        with self.assertRaisesRegex(ValueError, 'retained-master-model-not-registered'):
            retain._require_oca_models(env)


if __name__ == '__main__':
    unittest.main()
