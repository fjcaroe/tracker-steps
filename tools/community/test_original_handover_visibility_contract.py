"""Synthetic receipt boundaries; never certifies an engine or native access."""
from copy import deepcopy
import json
from types import SimpleNamespace
import unittest

import original_handover_visibility_contract as contract
import probe_original_master_visibility as source


DATABASE = 'MANAGEMENT_QA_CERRO_PAYROLL_API_ORIGINAL_HANDOVER_UNIT'


class Denied(Exception):
    pass


class ConfigurationModelFixture:
    def __init__(self, allowed):
        self.allowed = set(allowed)
        self.env = SimpleNamespace(su=False)
        self.read_fields = []

    def search(self, domain, order):
        return SimpleNamespace(ids=sorted(set(domain[0][2]) & self.allowed))

    def browse(self, ident):
        parent = self
        class Record:
            def read(self, fields):
                parent.read_fields.append(fields)
                if ident not in parent.allowed:
                    raise Denied('synthetic-normal-denial')
                return [{'id': ident}]
        return Record()


def fixture():
    capsule = {'tables': {}}
    counts = (4, 5, 10, 71, 30)
    for index, ((table, (model, fields)), count) in enumerate(zip(source.SPECS.items(), counts)):
        rows = []
        for offset in range(count):
            row = {name: None for name in fields}
            row['id'] = index * 100 + offset + 1
            if 'active' in row: row['active'] = True
            if 'type_id' in row: row['type_id'] = 101
            if 'struct_id' in row: row['struct_id'] = 1
            if 'category_id' in row: row['category_id'] = 401
            if table == 'hr_payroll_structure': row['report_id'] = 777
            rows.append(row)
        capsule['tables'][table] = {'model': model, 'row_count': count,
            'rows_json': [json.dumps(row) for row in rows]}
    projection = source.expected_projection(capsule)
    observations = {}
    for table, (model, fields) in source.SPECS.items():
        ids = [row['id'] for row in projection[table]]
        # Receipt-derived visibility deliberately uses IDs unrelated to BE3/4.
        allowed = set(ids) - ({102, 104} if model == 'hr.payroll.structure.type' else set())
        observations[model] = source.observe_model(ConfigurationModelFixture(allowed), ids, access_error=Denied)
    policy = {name: {'rows': 1, 'sha256': 'a' * 64} for name in contract.POLICY_TABLES}
    counters = {'ir_sequence_' + str(i): [1, 0, False] for i in range(1, 141)}
    proof = {'schema': 1, 'profile': 'source-native-original-master-id-visibility',
        'database': DATABASE.replace('_HANDOVER_', '_REFERENCE_'),
        'probe_sha256': next(iter(contract.SOURCE_OBSERVER_HASHES)), 'capsule_sha256': source.CAPSULE_SHA256,
        'transaction': {'read_only': True, 'odoo_cursor_readonly': True, 'isolation': 'repeatable read', 'local_primary': True},
        'engine': {'installed': 381, 'enterprise': 140, 'oca_installed': False, 'payslip_model_id': 602,
            'report_rows': [[777, 'hr.payslip']], 'module_metadata_sha256': 'b' * 64,
            'mro': ['odoo.addons.hr_payroll.models.hr_payslip.NativeMetadataFixture']},
        'actor': {'uid': 17, 'allowed_company_ids': [11, 12], 'active_company_id': 11,
            'original_company_memberships': [11, 12, 13], 'superuser': False, 'system_group_member': False,
            'original_native_payroll_manager': True, 'users_created': False, 'permissions_granted': False},
        'models': observations, 'original_sql_projection': projection,
        'original_sql_projection_sha256': contract.sha(source.encode(projection)),
        'original_projection_exact_after': True, 'normal_actor_source_visibility_proven': True,
        'master_orm_fields_read': ['id'], 'active_test': False, 'total_original_masters': 120,
        'allowed_master_ids': 118, 'denied_master_ids': 2,
        'policy_before': policy, 'policy_after': deepcopy(policy),
        'business_counters_before': counters, 'business_counters_after': deepcopy(counters)}
    for name in ('source_model_code_overridden', 'source_country_domain_evaluated_locally', 'historical_payroll_read',
        'salary_rules_evaluated', 'salary_amounts_read', 'formula_bodies_read_from_database', 'database_writes',
        'financial_certified', 'identity_conversion', 'all_products_operational', 'deadline_resolved'):
        proof[name] = False
    return capsule, proof


class OriginalVisibilityParityCase(unittest.TestCase):
    def validate(self, capsule, proof):
        return contract.validate_source(proof, capsule, target_database=DATABASE,
            original_model_id=602, original_report_ids={777})

    def test_source_partition_is_observed_and_target_must_reproduce_each_denial(self):
        capsule, proof = fixture()
        self.validate(capsule, proof)
        expected = proof['models']['hr.payroll.structure.type']
        model = ConfigurationModelFixture(expected['allowed_ids'])
        self.assertEqual(contract.compare_model(model, expected, access_error=Denied), expected)
        self.assertEqual(model.read_fields, [['id']] * 5)
        for allowed in (expected['capsule_ids'], [], expected['allowed_ids'][:-1]):
            with self.subTest(allowed=allowed), self.assertRaises(ValueError):
                contract.compare_model(ConfigurationModelFixture(allowed), expected, access_error=Denied)
        # A different SOURCE observation changes the contract; no country/ID
        # exception is baked into the target adapter.
        different = source.observe_model(ConfigurationModelFixture([101, 102, 104]),
            expected['capsule_ids'], access_error=Denied)
        self.assertEqual(contract.compare_model(ConfigurationModelFixture([101, 102, 104]),
            different, access_error=Denied), different)
        for allowed in ([101, 102, 103, 104, 105], [101, 102, 103, 105]):
            changed = deepcopy(proof)
            changed['models']['hr.payroll.structure.type'] = source.observe_model(
                ConfigurationModelFixture(allowed), expected['capsule_ids'], access_error=Denied)
            changed['allowed_master_ids'] = sum(len(row['allowed_ids']) for row in changed['models'].values())
            changed['denied_master_ids'] = sum(len(row['denied_ids']) for row in changed['models'].values())
            self.validate(capsule, changed)  # No constant118/2 admission rule.

    def test_wrong_epoch_actor_authority_context_or_projection_is_not_a_source_oracle(self):
        capsule, proof = fixture()
        for change in ('database', 'tool', 'capsule', 'readonly', 'sudo', 'system', 'grant', 'companies',
                       'projection', 'mro', 'financial', 'unproven', 'extra_model', 'partition', 'required_denial'):
            value = deepcopy(proof)
            if change == 'database': value['database'] += '_OTHER'
            elif change == 'tool': value['probe_sha256'] = 'c' * 64
            elif change == 'capsule': value['capsule_sha256'] = 'c' * 64
            elif change == 'readonly': value['transaction']['read_only'] = False
            elif change == 'sudo': value['actor']['superuser'] = True
            elif change == 'system': value['actor']['system_group_member'] = True
            elif change == 'grant': value['actor']['permissions_granted'] = True
            elif change == 'companies': value['actor']['allowed_company_ids'].append(99)
            elif change == 'projection': value['original_sql_projection']['hr_payroll_structure'][0]['id'] = 99
            elif change == 'mro': value['engine']['mro'].append('odoo.addons.payroll.models.Unexpected')
            elif change == 'financial': value['financial_certified'] = True
            elif change == 'unproven': value['normal_actor_source_visibility_proven'] = False
            elif change == 'extra_model': value['models']['unexpected.model'] = {}
            elif change == 'partition': value['models']['hr.payroll.structure.type']['denied_ids'].append(101)
            else:
                item = value['models']['hr.salary.rule']
                item['denied_ids'] = [item['allowed_ids'].pop()]
                item['search_ids'] = list(item['allowed_ids'])
                value['allowed_master_ids'] -= 1; value['denied_master_ids'] += 1
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.validate(capsule, value)

    def test_original_policy_and_counters_remain_strict_even_with_observed_source_denials(self):
        capsule, proof = fixture()
        self.validate(capsule, proof)
        policy, counters = deepcopy(proof['policy_before']), deepcopy(proof['business_counters_before'])
        counters['ir_sequence_999'] = [1, 0, False]
        report = contract.check_policy_and_counters(proof, policy, counters)
        self.assertEqual(report['original_business_counters_exact'], 140)
        self.assertEqual(report['new_target_counter_names'], ['ir_sequence_999'])
        self.assertFalse(report['original_policy_relaxed'])
        for change in ('policy', 'missing_policy', 'counter', 'missing_counter', 'source_policy_drift'):
            current_policy, current_counters, source_proof = deepcopy(policy), deepcopy(counters), deepcopy(proof)
            if change == 'policy': current_policy['res_groups']['sha256'] = 'c' * 64
            elif change == 'missing_policy': current_policy.pop('res_company_users_rel')
            elif change == 'counter': current_counters['ir_sequence_1'][0] += 1
            elif change == 'missing_counter': current_counters.pop('ir_sequence_1')
            else: source_proof['policy_after']['res_groups']['sha256'] = 'c' * 64
            with self.subTest(change=change), self.assertRaises(ValueError):
                contract.check_policy_and_counters(source_proof, current_policy, current_counters)


if __name__ == '__main__':
    unittest.main()
