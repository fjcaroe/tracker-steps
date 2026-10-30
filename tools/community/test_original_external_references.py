"""Synthetic metadata/edge plans only; no private data, Odoo or PostgreSQL."""
from copy import deepcopy
import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import original_external_references as audit


TYPE = 'hr.payroll.structure.type'
REPORT = 'ir.actions.report'


def field(name, kind, comodel=None, **extra):
    return dict({'name': name, 'type': kind, 'comodel': comodel, 'store': True,
        'company_dependent': False, 'relation_table': None, 'column1': None, 'column2': None,
        'inverse_name': None, 'model_field': None, 'related': [], 'selection_models': None,
        'selection_callable': False, 'discriminator_field': {'name': 'model_key', 'type': 'char',
            'store': True, 'compute': False, 'related': [], 'company_dependent': False} if kind == 'many2one_reference' else None}, **extra)


def fixture():
    scope = {TYPE: {'table': 'actual_types', 'ids': [1, 2, 3, 4]},
        REPORT: {'table': 'actual_reports', 'ids': [462]}}
    fs = [field('type_id', 'many2one', TYPE), field('action', 'reference'),
        field('record_id', 'many2one_reference', model_field='model_key'),
        field('type_ids', 'many2many', TYPE, relation_table='actual_rel', column1='owner_link', column2='type_link'),
        field('type_property', 'many2one', TYPE, company_dependent=True)]
    bindings = [(TYPE, 'actual_types', []), (REPORT, 'actual_reports', []),
        ('custom.owner', 'table_without_model_convention', fs)]
    registry = {'schema': 1, 'read_only': True, 'orm_loaded_by_payload': False,
        'orm_records_accessed': False, 'source_bodies_read': False, 'callables_executed': False,
        'database_writes': False, 'adoption_authorized': False,
        'models': [dict(model=model, table=table, fields=fields, abstract=False, auto=True, transient=False, inherits={})
            for model, table, fields in bindings]}
    tables = ('actual_types', 'actual_reports', 'table_without_model_convention', 'actual_rel')
    columns = [dict(table_name=table, name='id', sql_type='integer', not_null=True) for table in tables if table != 'actual_rel']
    columns += [dict(table_name='table_without_model_convention', name=name, sql_type=kind, not_null=False)
        for name, kind in (('type_id', 'integer'), ('action', 'character varying'), ('record_id', 'integer'),
            ('model_key', 'character varying'), ('type_property', 'jsonb'))]
    columns += [dict(table_name='actual_rel', name=name, sql_type='integer', not_null=True) for name in ('owner_link', 'type_link')]
    keys = [dict(table_name=table, name=table + '_pkey', columns=['id'], primary_key=True) for table in tables if table != 'actual_rel']
    keys += [dict(table_name='actual_rel', name='actual_pair_unique', columns=['owner_link', 'type_link'], primary_key=False)]
    foreign = [dict(name='scalar_fk', source_table='table_without_model_convention', source_columns=['type_id'], target_table='actual_types'),
        dict(name='rel_owner_fk', source_table='actual_rel', source_columns=['owner_link'], target_table='table_without_model_convention'),
        dict(name='rel_type_fk', source_table='actual_rel', source_columns=['type_link'], target_table='actual_types')]
    foreign = [dict(row, source_schema='public', target_schema='public', target_columns=['id'], validated=True, ondelete='r') for row in foreign]
    alias = {'id': 40001, 'module': 'hr_contract', 'name': 'structure_type_employee', 'model': TYPE, 'res_id': 1, 'noupdate': True}
    catalog = {'tables': [dict(name=table, schema='public', kind='r') for table in tables], 'columns': columns,
        'keys': keys, 'foreign_keys': foreign,
        'fields': [dict(id=index, model='custom.owner', name=row['name'], ttype=row['type'],
            relation=row['comodel'], store=True, company_dependent=row['company_dependent']) for index, row in enumerate(fs)],
        'alias_occupants': [alias], 'action_462': [{'id': 462, 'physical_table': 'actual_reports', 'type': REPORT}]}
    for model, selected in scope.items():
        catalog['target-occupants:' + model] = [dict(id=value, physical_table=selected['table'], row_sha256='0' * 64) for value in selected['ids']]
        catalog['target-aliases:' + model] = [alias] if model == TYPE else []
    return catalog, registry, scope, [alias]


class OriginalExternalReferencesCase(unittest.TestCase):
    def observations(self, catalog, registry, scope):
        queries, _, _ = audit.compile_paths(catalog, registry, scope)
        return {name: [] for name in queries}

    def test_runtime_bindings_compile_exact_fk_m2m_polymorphic_and_company_edges(self):
        catalog, registry, scope, aliases = fixture()
        queries, paths, blocked = audit.compile_paths(catalog, registry, scope)
        self.assertFalse(blocked)
        self.assertTrue({'physical-fk', 'registry-many2many', 'registry-reference',
            'registry-many2one-reference', 'registry-company-json'} <= {row['kind'] for row in paths})
        sql = '\n'.join(queries.values())
        self.assertIn('"table_without_model_convention"', sql)
        self.assertNotIn('"custom_owner"', sql)
        self.assertIn('"owner_link"', sql)
        self.assertIn('"type_link"', sql)
        self.assertIn('"model_key"=\'ir.actions.report\'', sql)
        self.assertIn("'ir.actions.report,462'", sql)
        self.assertIn('jsonb_each', sql)
        self.assertIn('company_id', sql)
        for query in queries.values():
            self.assertTrue(query.startswith('SELECT '))
            for verb in ('UPDATE ', 'INSERT ', 'DELETE ', 'ALTER ', 'CREATE ', 'DROP ', 'setval('):
                self.assertNotIn(verb, query)
        observations = self.observations(catalog, registry, scope)
        report = audit.assess(catalog, observations, deepcopy(observations), registry, scope, aliases)
        self.assertTrue(report['reference_closure_ready'])
        self.assertFalse(report['import_authorized'])
        self.assertFalse(report['id_reservation_authorized'])

    def test_missing_m2m_fks_owner_keys_and_discriminator_never_become_guesses(self):
        for edit, expected in (('fk', 'many2many-actual-table-column-fks-not-proven'),
                ('owner', 'owner-primary-or-nonnull-unique-key-not-proven'),
                ('discriminator', 'polymorphic-discriminator-binding-not-proven')):
            catalog, registry, scope, aliases = fixture()
            if edit == 'fk': catalog['foreign_keys'] = [row for row in catalog['foreign_keys'] if row['name'] != 'rel_owner_fk']
            elif edit == 'owner': catalog['keys'] = [row for row in catalog['keys'] if row['table_name'] != 'actual_rel']
            else: catalog['columns'] = [row for row in catalog['columns'] if row['name'] != 'model_key']
            queries, paths, blockers = audit.compile_paths(catalog, registry, scope)
            self.assertIn(expected, {row['code'] for row in blockers})
            report = audit.assess(catalog, {key: [] for key in queries}, {key: [] for key in queries}, registry, scope, aliases)
            self.assertFalse(report['reference_closure_ready'])

    def test_untyped_json_nonempty_values_remain_unbound_not_integer_matches(self):
        catalog, registry, scope, aliases = fixture()
        registry['models'][-1]['fields'].append(field('opaque_json', 'json'))
        catalog['columns'].append(dict(table_name='table_without_model_convention', name='opaque_json', sql_type='jsonb', not_null=False))
        observations = self.observations(catalog, registry, scope)
        key = next(name for name in observations if name.startswith('unclassified:'))
        observations[key] = [{'owner_pk': {'id': 9}, 'content_sha256': '1' * 64}]
        result = audit.assess(catalog, observations, deepcopy(observations), registry, scope, aliases)
        self.assertFalse(result['reference_closure_ready'])
        self.assertIn('untyped-json-without-reference-schema', {row['code'] for row in result['blockers']})
        self.assertFalse(next(row for row in result['paths'] if row['observation'] == key)['semantic_binding_proven'])

    def test_pk_alias_collision_action_occupant_and_missing_target_block_without_relocation(self):
        for edit in ('alias', 'action', 'missing'):
            catalog, registry, scope, aliases = fixture()
            if edit == 'alias':
                nominal = dict(aliases[0], id=50001)
                catalog['alias_occupants'] = [dict(aliases[0], module='foreign_owner', name='unrelated'), nominal]
            elif edit == 'action': catalog['action_462'][0]['type'] = 'ir.actions.act_window'
            else: catalog['target-occupants:' + TYPE].pop()
            before = self.observations(catalog, registry, scope)
            result = audit.assess(catalog, before, deepcopy(before), registry, scope, aliases)
            self.assertFalse(result['reference_closure_ready'])
            self.assertIsNone(result['selected_relocation_id'])
            self.assertTrue(all(row['write_authorized'] is False for row in result['alias_identity_plan']))

    def test_concurrent_rows_or_catalog_and_unclassified_json_are_fail_closed(self):
        catalog, registry, scope, aliases = fixture()
        first = self.observations(catalog, registry, scope)
        second = deepcopy(first)
        second[next(iter(second))] = [{'owner_pk': {'id': 7}, 'target_id': 1}]
        with self.assertRaisesRegex(ValueError, 'concurrent'):
            audit.assess(catalog, first, second, registry, scope, aliases)
        bad = deepcopy(registry)
        bad['models'][0]['table'] = 'guessed_table'
        with self.assertRaisesRegex(ValueError, 'model-table-binding'):
            audit.compile_paths(catalog, bad, scope)
        with self.assertRaises(ValueError):
            audit.ident('unsafe"; DROP TABLE business;--')

    def test_outbound_original_fk_discovers_exact_external_endpoint_without_adopting_it(self):
        catalog, registry, scope, aliases = fixture()
        registry['models'][0]['fields'].append(field('calendar_id', 'many2one', 'resource.calendar'))
        registry['models'].append(dict(model='resource.calendar', table='actual_calendars', fields=[],
            abstract=False, auto=True, transient=False, inherits={}))
        catalog['tables'].append(dict(name='actual_calendars', schema='public', kind='r'))
        catalog['columns'].append(dict(table_name='actual_types', name='calendar_id', sql_type='integer', not_null=False))
        catalog['foreign_keys'].append(dict(name='original_calendar_fk', source_schema='public', source_table='actual_types',
            source_columns=['calendar_id'], target_schema='public', target_table='actual_calendars',
            target_columns=['id'], validated=True, ondelete='n'))
        queries, paths, blockers = audit.compile_paths(catalog, registry, scope)
        path = next(path for path in paths if path['kind'] == 'outbound-original-fk')
        self.assertEqual((path['target_model'], path['target_table']), ('resource.calendar', 'actual_calendars'))
        self.assertIn('t.id IN (1,2,3,4)', queries[path['observation']])
        rows = {name: [] for name in queries}
        rows[path['observation']] = [{'owner_pk': {'id': 1}, 'target_model': 'resource.calendar', 'target_id': 77, 'company_id': None}]
        endpoint_queries, contracts = audit.endpoint_queries(paths, rows, registry)
        self.assertEqual(contracts[0]['ids'], [77])
        self.assertIn('"actual_calendars"', endpoint_queries[contracts[0]['observation']])
        self.assertNotIn('resource.calendar', scope)

    def test_outbound_original_json_m2m_and_polymorphic_edges_do_not_need_capsule_enumeration(self):
        catalog, registry, scope, aliases = fixture()
        for model, table in (('external.master', 'actual_external_storage'), ('res.company', 'actual_company_storage')):
            registry['models'].append(dict(model=model, table=table, fields=[],
                abstract=False, auto=True, transient=False, inherits={}))
            catalog['tables'].append(dict(name=table, schema='public', kind='r'))
        additions = [field('company_property', 'many2one', 'external.master', company_dependent=True),
            field('external_ids', 'many2many', 'external.master', relation_table='original_external_rel',
                column1='original_id', column2='external_id'),
            field('external_ref', 'reference'), field('external_key', 'many2one_reference', model_field='model_key')]
        registry['models'][0]['fields'].extend(additions)
        catalog['fields'].extend(dict(id=100 + index, model=TYPE, name=row['name'], ttype=row['type'],
            relation=row['comodel'], store=True, company_dependent=row['company_dependent']) for index, row in enumerate(additions))
        catalog['columns'].extend(dict(table_name='actual_types', name=name, sql_type=kind, not_null=False)
            for name, kind in (('company_property', 'jsonb'), ('external_ref', 'text'),
                ('external_key', 'integer'), ('model_key', 'character varying')))
        catalog['tables'].append(dict(name='original_external_rel', schema='public', kind='r'))
        catalog['columns'].extend(dict(table_name='original_external_rel', name=name, sql_type='integer', not_null=True)
            for name in ('original_id', 'external_id'))
        catalog['keys'].append(dict(table_name='original_external_rel', name='original_external_unique',
            columns=['original_id', 'external_id'], primary_key=False))
        catalog['foreign_keys'].extend(dict(name='out_' + name, source_schema='public', source_table='original_external_rel',
            source_columns=[name], target_schema='public', target_table=table, target_columns=['id'],
            validated=True, ondelete='r') for name, table in (('original_id', 'actual_types'), ('external_id', 'actual_external_storage')))
        queries, paths, blockers = audit.compile_paths(catalog, registry, scope)
        self.assertFalse(blockers)
        rows = {key: [] for key in queries}
        kinds = ('registry-many2many', 'registry-company-json', 'outbound-original-reference', 'outbound-original-many2one-reference')
        selected = [row for row in paths if row['kind'] in kinds and row['table'] in ('actual_types', 'original_external_rel')]
        self.assertEqual(len(selected), 4)
        for path in selected:
            self.assertIn('IN (1,2,3,4)', queries[path['observation']])
            rows[path['observation']] = [{'owner_pk': {'original_id': 1, 'external_id': 77} if path['kind'] == 'registry-many2many' else {'id': 1},
                'target_model': 'external.master', 'target_id': 77,
                'company_id': 9 if path['kind'] == 'registry-company-json' else None}]
        json_path = next(path for path in selected if path['kind'] == 'registry-company-json')
        rows[json_path['observation']].append({'owner_pk': {'id': 1}, 'target_model': 'external.master',
            'target_id': None, 'company_id': 10})
        self.assertIn("j.value='null'::jsonb", queries[json_path['observation']])
        self.assertIn('BETWEEN 1 AND 2147483647', queries[json_path['observation']])
        _, endpoints = audit.endpoint_queries(paths, rows, registry)
        external = next(row for row in endpoints if row['model'] == 'external.master')
        company = next(row for row in endpoints if row['model'] == 'res.company')
        self.assertEqual((external['table'], external['ids']), ('actual_external_storage', [77]))
        self.assertEqual((company['table'], company['ids']), ('actual_company_storage', [9, 10]))
        self.assertNotIn('external.master', scope)
        expanded = deepcopy(scope)
        expanded['external.master'] = {'table': 'actual_external_storage', 'ids': [3]}
        expanded_queries, expanded_paths, expanded_blockers = audit.compile_paths(catalog, registry, expanded)
        self.assertFalse(expanded_blockers)
        rel_path = next(path for path in expanded_paths if path['kind'] == 'registry-many2many' and path['table'] == 'original_external_rel')
        self.assertIn('"external_id" IN (3) OR t."original_id" IN (1,2,3,4)', expanded_queries[rel_path['observation']])
        unknown = deepcopy(rows)
        dynamic = next(path for path in selected if path.get('target_model_from_row'))
        unknown[dynamic['observation']][0]['target_model'] = 'unloaded.master'
        with self.assertRaisesRegex(ValueError, 'polymorphic-target-registry-binding'):
            audit.endpoint_queries(paths, unknown, registry)
        missing_company = deepcopy(registry)
        missing_company['models'] = [row for row in missing_company['models'] if row['model'] != 'res.company']
        with self.assertRaisesRegex(ValueError, 'company-endpoint-registry-binding'):
            audit.endpoint_queries(paths, rows, missing_company)

    def test_outbound_original_unloaded_comodel_is_blocked_before_reference_queries(self):
        catalog, registry, scope, _ = fixture()
        registry['models'][0]['fields'].append(field('unavailable_id', 'many2one', 'unloaded.master'))
        _, _, blockers = audit.compile_paths(catalog, registry, scope)
        self.assertIn('outbound-original-comodel-not-in-loaded-registry', {row['code'] for row in blockers})

    def test_occupied_action462_outgoing_fk_is_bound_without_authorizing_relocation(self):
        catalog, registry, scope, _ = fixture()
        action = 'ir.actions.act_window'
        scope[action] = {'table': 'actual_windows', 'ids': [462], 'original_expected': False}
        for model, table, fields in ((action, 'actual_windows', [field('view_id', 'many2one', 'ir.ui.view')]),
                ('ir.ui.view', 'actual_views', [])):
            registry['models'].append(dict(model=model, table=table, fields=fields,
                abstract=False, auto=True, transient=False, inherits={}))
            catalog['tables'].append(dict(name=table, schema='public', kind='r'))
            catalog['columns'].append(dict(table_name=table, name='id', sql_type='integer', not_null=True))
            catalog['keys'].append(dict(table_name=table, name=table + '_pkey', columns=['id'], primary_key=True))
        catalog['columns'].append(dict(table_name='actual_windows', name='view_id', sql_type='integer', not_null=False))
        catalog['fields'].append(dict(id=200, model=action, name='view_id', ttype='many2one', relation='ir.ui.view', store=True, company_dependent=False))
        catalog['foreign_keys'].append(dict(name='occupied_action_view_fk', source_schema='public', source_table='actual_windows',
            source_columns=['view_id'], target_schema='public', target_table='actual_views', target_columns=['id'], validated=True, ondelete='n'))
        queries, paths, blockers = audit.compile_paths(catalog, registry, scope)
        self.assertFalse(blockers)
        path = next(path for path in paths if path['kind'] == 'outbound-original-fk' and path['table'] == 'actual_windows')
        self.assertEqual((path['target_model'], path['target_table']), ('ir.ui.view', 'actual_views'))
        self.assertIn('t.id IN (462)', queries[path['observation']])

    def test_runtime_policy_requires_real_readonly_cursors_and_exact_infrastructure(self):
        database = 'COMMUNITY_PAYROLL_API_SYNTHETIC'
        calls = [{'database': database, 'odoo_cursor_readonly': True, 'transaction_read_only': 'on', 'pg_is_in_recovery': False}]
        reader = {'original_get_sequences_sha256': audit.SEQUENCE_METHOD_SHA256,
            'select_only_sql_sha256': audit.SEQUENCE_SELECT_SHA256,
            'original_registry_source_sha256': audit.REGISTRY_SOURCE_SHA256['community'],
            'cache_keys': ['default', 'assets', 'templates', 'routing', 'groups'], 'calls': calls,
            'installed_sources_modified': False, 'cursor_readonly_unchanged': True,
            'setup_signaling_unchanged': True, 'signal_changes_unchanged': True, 'nextval_unchanged': True}
        before = {name: {'sequence': 7} for name in ['base_registry_signaling']
            + ['base_cache_signaling_' + key for key in reader['cache_keys']]}
        before['actual_original_master'] = {'rows': 120, 'md5': '0' * 32}
        registry = {'database': database, 'readonly_sequence_reader': reader, 'readonly_cursor_proof': calls}
        accepted = {'database': database, 'mode': 'community'}
        receipt = dict(schema=1, database=database, mode='community', readonly_sequence_reader=reader,
            public_snapshots_count=len(before), upgraded=False, adoption_authorized=False)
        receipt.update({name: True for name in ('all_tables_and_sequences_exact', 'all_infrastructure_sequences_also_exact',
            'external_network_disabled', 'postgres_unix_socket', 'odoo_pool_readonly_before_connect', 'read_only_before_registry_startup')})
        result = audit.runtime_contract(receipt, registry, accepted, before, deepcopy(before))
        self.assertFalse(result['adoption_authorized'])
        for change in ('counter', 'rw', 'replica', 'writer', 'policy', 'before-connect', 'wrong-db', 'upgrade'):
            with self.subTest(change=change):
                r, metadata, after = deepcopy(receipt), deepcopy(registry), deepcopy(before)
                if change == 'counter': after['base_registry_signaling'] = {'sequence': 8}
                elif change == 'rw': r['readonly_sequence_reader']['calls'][0]['transaction_read_only'] = 'off'
                elif change == 'replica': r['readonly_sequence_reader']['calls'][0]['pg_is_in_recovery'] = True
                elif change == 'writer': r['readonly_sequence_reader']['nextval_unchanged'] = False
                elif change == 'policy': r['readonly_sequence_reader']['select_only_sql_sha256'] = 'a' * 64
                elif change == 'before-connect': r['odoo_pool_readonly_before_connect'] = False
                elif change == 'wrong-db': r['database'] = 'CERROELPLOMO'
                elif change == 'upgrade': r['upgraded'] = True
                # A matching copied metadata claim does not make an unsafe
                # cursor, changed counter, policy or startup acceptable.
                metadata['readonly_sequence_reader'] = deepcopy(r['readonly_sequence_reader'])
                with self.assertRaises(ValueError):
                    audit.runtime_contract(r, metadata, accepted, before, after)

    def test_connection_guard_is_local_readonly_and_rejects_mutation_before_process(self):
        with patch.object(audit.subprocess, 'run') as run:
            for database, sql in (('CERROELPLOMO', 'SELECT 1'),
                    ('COMMUNITY_PAYROLL_API_SYNTHETIC', 'UPDATE private_table SET id=1')):
                with self.assertRaises(ValueError):
                    audit.run_snapshot(database, {'probe': sql})
            run.assert_not_called()
            run.return_value = SimpleNamespace(returncode=0, stdout='{"section":"transaction","rows":[{"mode":"on"}]}\n')
            result = audit.run_snapshot('COMMUNITY_PAYROLL_API_SYNTHETIC', {'transaction': "SELECT current_setting('transaction_read_only') AS mode"})
            command = run.call_args.args[0]
            self.assertIn('PGHOST=/var/run/postgresql', command)
            self.assertIn('PGOPTIONS=-c default_transaction_read_only=on', command)
            self.assertIn('PGPASSFILE=/opt/steps-validation/no-such-readonly-passfile', command)
            self.assertEqual(result, {'transaction': [{'mode': 'on'}]})

    def test_four_canonical_types_and_three_reference_aliases_are_not_relocated_as_originals(self):
        originals = [dict(id=100 + ident, module='hr_contract', name=name, model=TYPE, res_id=ident, noupdate=True)
            for ident, name in enumerate(audit.TYPE_ALIASES, 1)]
        originals += [dict(id=200 + ident, module='synthetic_original', name='master_%s' % ident,
            model=TYPE, res_id=5, noupdate=False) for ident in range(84)]
        references = [dict(id=900 + ident, module='synthetic_reference', name='adapter_%s' % ident,
            model=TYPE, res_id=5, noupdate=False) for ident in range(3)]
        report = dict(id=999, module='hr_payroll', name='action_report_payslip', model=REPORT, res_id=462, noupdate=False)
        capsule = {'xmlids': originals + references}
        snapshot = {'original_xmlids': originals + [report]}
        source, extra = audit.original_aliases(capsule, snapshot)
        self.assertEqual((len(source), len(extra)), (89, 3))
        self.assertEqual(extra, references)
        for edit in ('id', 'noupdate', 'model'):
            changed = deepcopy(snapshot)
            changed['original_xmlids'][0][edit] = 1000 if edit == 'id' else False if edit == 'noupdate' else 'other.model'
            with self.assertRaises(ValueError):
                audit.original_aliases(capsule, changed)


if __name__ == '__main__':
    unittest.main()
