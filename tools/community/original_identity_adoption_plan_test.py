"""Identity planning is not overwrite/relocation/adoption authorization."""
import copy
import json
import unittest
from unittest.mock import patch

import original_identity_adoption_plan as audit


class IdentityPlanCase(unittest.TestCase):
    def inputs(self):
        capsule = {'tables': {table: {'row_count': count, 'rows_sha256': table + '-sealed'}
            for table, count in zip(audit.gate.TABLES, (4, 5, 6, 71, 34))}}
        values = [{'id': ident, 'field': field, 'json_type': kind, 'is_null': null,
                   'value_md5': str(ident) + field}
            for ident in audit.TYPE_IDS
            for field, kind, null in (('id', 'number', False), ('name', 'string', False),
                ('country_id', 'null', True), ('default_schedule_pay', 'string', False),
                ('write_date', 'string', False))]
        aliases = [{'id': 41749 + ident, 'module': 'hr_contract', 'name': name,
            'model': audit.TYPE_MODEL, 'res_id': ident, 'noupdate': True}
            for ident, name in zip(audit.TYPE_IDS, audit.TYPE_ALIASES)]
        aliases += [{'id': 999, 'module': 'hr_payroll', 'name': 'action_report_payslip',
                     'model': 'ir.actions.report', 'res_id': 462, 'noupdate': False}]
        source = {'expected_type_value_hashes': values, 'type_value_hashes': copy.deepcopy(values),
            'identity_aliases': aliases, 'action_462': [{'physical_table': 'ir_act_report_xml', 'id': 462, 'type': 'ir.actions.report'}]}
        for table, row in capsule['tables'].items():
            source['source_hash:' + table] = [{'rows_sha256': row['rows_sha256']}]
        target = copy.deepcopy(source)
        for row in target['identity_aliases']:
            row['id'] += 1000
        target['identity_aliases'][-1] = {'id': 28, 'module': 'calendar', 'name': 'other_action',
            'model': 'ir.actions.act_window', 'res_id': 462, 'noupdate': False}
        target['action_462'] = [{'physical_table': 'ir_act_window', 'id': 462, 'type': 'ir.actions.act_window'}]
        return capsule, source, target

    def plan(self, capsule, source, target):
        return audit.plan(capsule, source, target, paths={'source': [], 'target': []},
            unresolved={'source': [], 'target': []})

    def test_common_official_seed_alias_is_distinct_from_adopted_metadata_identity(self):
        capsule, source, target = self.inputs()
        report = self.plan(capsule, source, target)
        self.assertEqual(report['source_master_count'], 120)
        self.assertEqual(report['source_rule_count'], 71)
        self.assertTrue(all(row['shared_official_seed_candidate'] for row in report['types']))
        self.assertTrue(all(not row['original_xmlid_metadata_pk_equal'] for row in report['types']))
        self.assertTrue(all(not row['overwrite_authorized'] and not row['relocation_authorized'] for row in report['types']))
        self.assertFalse(report['adoption_ready'])
        self.assertFalse(report['import_authorized'])
        self.assertIsNone(report['action_strategy']['selected_relocation_id'])
        self.assertIn('original-official-type-xmlid-metadata-primary-key-not-adopted', report['blockers'])
        self.assertIn('serialized-runtime-and-integer-embedded-reference-contract-not-certified', report['blockers'])

    def test_wrong_alias_owner_model_pointer_or_noupdate_never_becomes_shared_identity(self):
        for key, wrong in (('module', 'other'), ('model', 'other.model'), ('res_id', 40), ('noupdate', False)):
            with self.subTest(key=key):
                capsule, source, target = self.inputs()
                target['identity_aliases'][0][key] = wrong
                report = self.plan(capsule, source, target)
                self.assertFalse(report['types'][0]['shared_official_seed_candidate'])
                self.assertIn('official-type-canonical-alias-or-noupdate-differs', report['blockers'])

    def test_values_are_classified_without_exporting_them_or_inventing_ownership(self):
        capsule, source, target = self.inputs()
        for row in target['type_value_hashes']:
            if row['id'] == 1 and row['field'] in ('country_id', 'default_schedule_pay', 'write_date'):
                row['value_md5'] += '-different'
        target['type_value_hashes'].append({'id': 1, 'field': 'company_id', 'json_type': 'null', 'is_null': True, 'value_md5': 'nullhash'})
        report = self.plan(capsule, source, target)
        changed = {row['field']: row for row in report['types'][0]['field_comparisons'] if not row['equal']}
        self.assertEqual(changed['country_id']['classification'], 'business-identity-difference-not-authorized')
        self.assertEqual(changed['default_schedule_pay']['classification'], 'policy-or-default-difference-requires-original-adoption')
        self.assertEqual(changed['write_date']['classification'], 'original-audit-identity-not-adopted')
        self.assertEqual(report['types'][0]['target_only_fields'][0]['field'], 'company_id')
        self.assertTrue(all(row['write_authorized'] is False for row in changed.values()))

    def test_source_hash_or_original_alias_drift_blocks_before_plan(self):
        for mutation in ('type', 'all-master', 'alias'):
            with self.subTest(mutation=mutation):
                capsule, source, target = self.inputs()
                if mutation == 'type': source['type_value_hashes'][0]['value_md5'] = 'changed'
                elif mutation == 'all-master': source['source_hash:hr_salary_rule'][0]['rows_sha256'] = 'changed'
                else: source['identity_aliases'][0]['noupdate'] = False
                with self.assertRaises(audit.gate.PreflightError): self.plan(capsule, source, target)

    def metadata(self):
        return {'physical_columns': [
            {'table_name': 'hr_contract', 'column_name': 'id', 'sql_type': 'integer'},
            {'table_name': 'hr_contract', 'column_name': 'structure_type_id', 'sql_type': 'integer'},
            {'table_name': 'ir_ui_menu', 'column_name': 'id', 'sql_type': 'integer'},
            {'table_name': 'ir_ui_menu', 'column_name': 'action', 'sql_type': 'character varying'}],
            'inbound_foreign_keys': [{'name': 'kind_fk', 'source_schema': 'public', 'source_table': 'hr_contract',
                'target_schema': 'public', 'target_table': 'hr_payroll_structure_type',
                'source_columns': ['structure_type_id'], 'target_columns': ['id'], 'validated': True}],
            'identity_relation_fields': [{'model': 'ir.ui.menu', 'name': 'action', 'store': True,
                'ttype': 'reference', 'relation': None}]}

    def test_declared_fk_and_reference_queries_never_read_amounts_or_execute_writes(self):
        queries, paths, unresolved = audit.reference_queries(self.metadata())
        self.assertEqual(len(paths), 2)
        self.assertEqual(unresolved, [])
        self.assertTrue(all(query.startswith('SELECT ') for query in queries.values()))
        self.assertTrue(all('to_jsonb(t)' not in query and 'wage' not in query for query in queries.values()))
        self.assertIn('IN (1,2,3,4)', queries['path:fk:0'])
        self.assertIn('ir[.]actions[.]', next(query for key, query in queries.items() if 'polymorphic' in key))
        self.assertTrue(paths[0]['owner_record_ids_bound'])
        self.assertFalse(paths[1]['table_mapping_certified'])

    def test_unknown_runtime_binding_and_composite_keys_remain_visible_blockers(self):
        data = self.metadata()
        data['inbound_foreign_keys'][0]['target_columns'] = ['id', 'company_id']
        data['identity_relation_fields'].append({'model': 'custom.override.table', 'name': 'kind_id',
            'store': True, 'ttype': 'many2one', 'relation': audit.TYPE_MODEL})
        queries, _, missing = audit.reference_queries(data)
        self.assertEqual(len(missing), 2)
        self.assertNotIn('path:fk:0', queries)
        self.assertIn('unreviewed-schema-or-composite-reference', [row['blocker'] for row in missing])
        self.assertIn('stored-field-has-no-proven-physical-model-table-binding', [row['blocker'] for row in missing])

    def test_declared_many2one_without_fk_is_counted_but_remains_unproven(self):
        data = self.metadata()
        data['inbound_foreign_keys'] = []
        data['identity_relation_fields'] = [{'model': 'hr.contract', 'name': 'structure_type_id',
            'store': True, 'ttype': 'many2one', 'relation': audit.TYPE_MODEL, 'company_dependent': False}]
        queries, paths, missing = audit.reference_queries(data)
        self.assertEqual(len(paths), 1)
        self.assertEqual(paths[0]['path_kind'], 'declared-many2one-without-foreign-key-candidate')
        self.assertFalse(paths[0]['table_mapping_certified'])
        self.assertIn('IN (1,2,3,4)', queries['path:declared:0'])
        self.assertEqual(missing[0]['blocker'], 'stored-relation-without-reviewed-physical-foreign-key')

    def test_capsule_values_are_only_hex_sql_literals_never_formula_evaluation(self):
        raw = [json.dumps({'id': ident, 'name': "'); DELETE FROM private; --"}) for ident in audit.TYPE_IDS]
        capsule = {'tables': {'hr_payroll_structure_type': {'rows_json': raw}}}
        with patch.object(audit.gate, 'capsule_rows', return_value={'hr_payroll_structure_type': [json.loads(row) for row in raw]}):
            query = audit.expected_field_query(capsule)
        self.assertNotIn('DELETE', query)
        self.assertIn('decode(', query)
        self.assertIn('md5(j.value::text)', query)
        with self.assertRaises(audit.gate.PreflightError): audit.identifier('x;DELETE')


if __name__ == '__main__':
    unittest.main()
