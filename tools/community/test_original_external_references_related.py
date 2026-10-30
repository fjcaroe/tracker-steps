"""Synthetic metadata/observations; never starts ORM, reads bodies or writes SQL."""
from copy import deepcopy
import unittest

import original_external_references as audit
import original_external_references_related as related
from test_original_external_references import field, fixture


def related_fixture():
    catalog, registry, scope, aliases = fixture()
    owner = registry['models'][-1]
    reference = next(row for row in owner['fields'] if row['type'] == 'many2one_reference')
    reference['discriminator_field'].update(compute=True, related=['res_model_id', 'model'])
    owner['fields'].append(field('res_model_id', 'many2one', 'ir.model'))
    registry['models'].append(dict(model='ir.model', table='physical_model_namespace', fields=[],
        abstract=False, auto=True, transient=False, inherits={}))
    catalog['tables'].append(dict(name='physical_model_namespace', schema='public', kind='r'))
    catalog['columns'] += [dict(table_name='table_without_model_convention', name='res_model_id', sql_type='integer', not_null=False),
        dict(table_name='physical_model_namespace', name='id', sql_type='integer', not_null=True),
        dict(table_name='physical_model_namespace', name='model', sql_type='character varying', not_null=True)]
    catalog['keys'] += [dict(table_name='physical_model_namespace', name='namespace_pkey', columns=['id'], primary_key=True),
        dict(table_name='physical_model_namespace', name='namespace_model_unique', columns=['model'], primary_key=False)]
    catalog['fields'].append(dict(id=100, model='custom.owner', name='res_model_id', ttype='many2one', relation='ir.model',
        store=True, company_dependent=False))
    catalog['foreign_keys'].append(dict(name='actual_namespace_fk', source_schema='public', source_table='table_without_model_convention',
        source_columns=['res_model_id'], target_schema='public', target_table='physical_model_namespace', target_columns=['id'],
        validated=True, ondelete='r'))
    return catalog, registry, scope, aliases, owner, reference


class RelatedDiscriminatorCase(unittest.TestCase):
    def test_offline_contrast_closes_exactly_three_guards_and_preserves_all_old_observations(self):
        baseline = {key: 'same' for key in ('database', 'capsule_sha256', 'backup_sha256', 'acceptance_sha256',
            'registry_proof_sha256', 'source_packet_sha256', 'installation_postflight_sha256')}
        baseline.update(read_only=True, database_writes=False, import_authorized=False, id_reservation_authorized=False,
            two_snapshots_exact=True, scope={}, target_identities={}, alias_identity_plan=[], original_master_value_hashes={},
            original_xmlids_backup_proof={}, registry_runtime_proof={}, paths=[{'kind': 'existing-path', 'table': 'original',
                'field': 'type_id', 'observation': 'edge:0', 'rows': [{'owner_pk': {'id': 19}, 'target_id': 1}]}],
            observations={key: [] for key in ('transaction', 'database', 'modules', 'pending', 'tables', 'columns', 'keys',
                'foreign_keys', 'fields', 'alias_occupants', 'action_462', 'action_family')}, blockers=[
                {'code': 'polymorphic-discriminator-binding-not-proven', 'model': model, 'field': 'res_id'} for model in related.EXPECTED]
                + [{'code': 'another-unresolved-contract'}])
        current = deepcopy(baseline); current['blockers'] = current['blockers'][-1:]
        for index, model in enumerate(related.EXPECTED):
            name = 'invalid:' + str(index)
            current['paths'].append({'kind': 'stored-related-discriminator-mismatch', 'rows': [], 'observation': name,
                'discriminator_binding': {'owner_model': model}})
            current['paths'].append({'kind': 'registry-related-discriminator-link', 'owner_model': model,
                'observation': 'lineage:' + str(index), 'runtime_equality_observation': name, 'rows': [], 'discriminator_binding': {
                    'runtime_equality_observation_required': True, 'namespace_table': 'physical_registry_model'}})
        receipt = related.compare(baseline, current)
        self.assertEqual((receipt['blockers_before'], receipt['blockers_after']), (4, 1))
        self.assertFalse(receipt['adoption_authorized'])
        for change in ('identity', 'catalog', 'old_path', 'unrelated_guard', 'mismatch', 'missing_lineage', 'write'):
            altered = deepcopy(current)
            if change == 'identity': altered['source_packet_sha256'] = 'different'
            elif change == 'catalog': altered['observations']['keys'] = [{'table_name': 'changed'}]
            elif change == 'old_path': altered['paths'][0]['rows'][0]['target_id'] = 2
            elif change == 'unrelated_guard': altered['blockers'] = []
            elif change == 'mismatch': altered['paths'][1]['rows'] = [{'owner_pk': {'id': 1}}]
            elif change == 'missing_lineage': altered['paths'].pop(2)
            elif change == 'write': altered['database_writes'] = True
            with self.subTest(change=change), self.assertRaises(ValueError):
                related.compare(baseline, altered)

    def test_typed_relation_requires_actual_foreign_key_and_never_guesses_or_executes(self):
        catalog, registry, scope, _, _, reference = related_fixture()
        models = audit.registry_models(registry)
        contract = related.resolve(catalog, models, 'custom.owner', reference)
        self.assertTrue(contract['proven'])
        self.assertEqual(contract['namespace_table'], 'physical_model_namespace')
        self.assertTrue(contract['runtime_equality_observation_required'])
        self.assertFalse(contract['computes_executed'])
        queries, paths, blockers = audit.compile_paths(catalog, registry, scope)
        self.assertFalse(blockers)
        link = next(path for path in paths if path['kind'] == 'registry-related-discriminator-link')
        mismatch = next(path for path in paths if path['kind'] == 'stored-related-discriminator-mismatch')
        sql = queries[mismatch['observation']]
        self.assertIn('LEFT JOIN ONLY public."physical_model_namespace" r ON r.id=t."res_model_id"', sql)
        self.assertIn('t."model_key" IS DISTINCT FROM r."model"', sql)
        self.assertIn('r.id IS NULL', sql)
        self.assertNotIn('public."ir_model"', sql)
        self.assertEqual(link['target_model'], 'ir.model')
        self.assertEqual(link['runtime_equality_observation'], mismatch['observation'])
        self.assertTrue(all(query.startswith('SELECT ') for query in queries.values()))

    def test_metadata_only_or_observed_mismatch_never_closes_the_runtime_guard(self):
        catalog, registry, scope, aliases, _, _ = related_fixture()
        queries, paths, _ = audit.compile_paths(catalog, registry, scope)
        observed = {name: [] for name in queries}
        mismatch = next(path for path in paths if path['kind'] == 'stored-related-discriminator-mismatch')
        missing = dict(observed); missing.pop(mismatch['observation'])
        with self.assertRaisesRegex(ValueError, 'observations-incomplete'):
            audit.assess(catalog, missing, deepcopy(missing), registry, scope, aliases)
        result = audit.assess(catalog, observed, deepcopy(observed), registry, scope, aliases)
        self.assertTrue(result['reference_closure_ready'])
        self.assertFalse(result['import_authorized'])
        observed[mismatch['observation']] = [{'owner_pk': {'id': 7, '_physical_table': 'table_without_model_convention'},
            'namespace_record_id': 19, 'stored_discriminator_sha256': None, 'related_discriminator_sha256': 'a' * 64}]
        result = audit.assess(catalog, observed, deepcopy(observed), registry, scope, aliases)
        self.assertFalse(result['reference_closure_ready'])
        self.assertIn('stored-related-discriminator-mismatch', {row['code'] for row in result['blockers']})

    def test_unstored_arbitrary_multihop_untyped_ambiguous_or_stale_metadata_stays_blocked(self):
        for change in ('unstored', 'arbitrary', 'not_compute', 'company', 'multihop', 'wrong_leaf',
                'related_link', 'unregistered_namespace', 'view', 'nullable_model', 'nontext_model', 'no_unique',
                'missing_fk', 'unvalidated_fk', 'duplicate_fk', 'foreign_schema', 'wrong_declared_model'):
            with self.subTest(change=change):
                catalog, registry, scope, _, owner, reference = related_fixture()
                proof = reference['discriminator_field']
                if change == 'unstored': proof['store'] = False
                elif change == 'arbitrary': proof['related'] = []
                elif change == 'not_compute': proof['compute'] = False
                elif change == 'company': proof['company_dependent'] = True
                elif change == 'multihop': proof['related'] = ['res_model_id', 'another', 'model']
                elif change == 'wrong_leaf': proof['related'][1] = 'name'
                elif change == 'related_link': owner['fields'][-1]['related'] = ['another_id']
                elif change == 'unregistered_namespace': registry['models'].pop()
                elif change == 'view': catalog['tables'][-1]['kind'] = 'v'
                elif change == 'nullable_model': catalog['columns'][-1]['not_null'] = False
                elif change == 'nontext_model': catalog['columns'][-1]['sql_type'] = 'jsonb'
                elif change == 'no_unique': catalog['keys'].pop()
                elif change == 'missing_fk': catalog['foreign_keys'].pop()
                elif change == 'unvalidated_fk': catalog['foreign_keys'][-1]['validated'] = False
                elif change == 'duplicate_fk': catalog['foreign_keys'].append(deepcopy(catalog['foreign_keys'][-1]))
                elif change == 'foreign_schema': catalog['foreign_keys'][-1]['target_schema'] = 'other'
                elif change == 'wrong_declared_model': catalog['fields'][-1]['relation'] = 'unrelated.model'
                self.assertFalse(related.resolve(catalog, audit.registry_models(registry), 'custom.owner', reference)['proven'])
                _, paths, blockers = audit.compile_paths(catalog, registry, scope)
                self.assertIn('polymorphic-discriminator-binding-not-proven', {row['code'] for row in blockers})
                self.assertFalse(any(path['kind'] == 'registry-related-discriminator-link' for path in paths))


if __name__ == '__main__':
    unittest.main()
