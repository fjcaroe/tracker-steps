"""Readonly identity plan for four official payroll types and original report462.

No imports/adoption, relocation, sequence reservation, ORM, DDL or DML. Selected
master values become PostgreSQL JSON type/NULL/hash evidence, never raw values.
Catalogues reveal declared paths; serialized/runtime paths remain explicit gates.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat

import payroll_configuration_adoption_preflight as gate
import payroll_original_security_admission as security


TYPE_MODEL = 'hr.payroll.structure.type'
TYPE_IDS = (1, 2, 3, 4)
TYPE_ALIASES = ('structure_type_employee', 'structure_type_worker',
                'structure_type_employee_cp200_pfi', 'structure_type_employee_cp200')
AUDIT_FIELDS = {'create_date', 'write_date', 'create_uid', 'write_uid'}
POLICY_FIELDS = {'default_schedule_pay', 'default_resource_calendar_id', 'default_work_entry_type_id',
                 'default_struct_id', 'wage_type', 'sequence'}
IDENTITY_FIELDS = {'name', 'country_id'}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def identifier(name):
    gate.require(re.fullmatch(r'[a-z_][a-z_0-9]*', name), 'unreviewed-catalog-identifier')
    return '"' + name + '"'


def type_field_hashes(relation):
    return "SELECT t.id,j.key AS field,jsonb_typeof(j.value) AS json_type,j.value='null'::jsonb AS is_null,md5(j.value::text) AS value_md5 FROM " + relation + " CROSS JOIN LATERAL jsonb_each(to_jsonb(t)) j WHERE t.id IN (1,2,3,4) ORDER BY t.id,j.key"


def expected_field_query(capsule):
    rows = gate.capsule_rows(capsule)['hr_payroll_structure_type']
    selected = [raw for raw in capsule['tables']['hr_payroll_structure_type']['rows_json']
        if json.loads(raw)['id'] in TYPE_IDS]
    gate.require(len(selected) == 4 and {row['id'] for row in rows if row['id'] in TYPE_IDS} == set(TYPE_IDS), 'original-four-type-identities-missing')
    values = ','.join("(convert_from(decode('%s','hex'),'UTF8')::jsonb)" % raw.encode().hex() for raw in selected)
    return "WITH originals(payload) AS (VALUES " + values + ") SELECT (payload->>'id')::integer AS id,j.key AS field,jsonb_typeof(j.value) AS json_type,j.value='null'::jsonb AS is_null,md5(j.value::text) AS value_md5 FROM originals CROSS JOIN LATERAL jsonb_each(payload) j ORDER BY id,j.key"


def metadata_queries(capsule, *, source):
    # Existing versioned gate hashes all120 masters/71 rules, original aliases,
    # fields/ACL and empty original M2M without returning salary formula bodies.
    statements = gate.queries(capsule, source=source)
    statements.update({name: query for name, query in security.security_queries(capsule).items()
        if name.startswith('security_')})
    statements.update({
        'type_value_hashes': type_field_hashes('public.hr_payroll_structure_type t'),
        'expected_type_value_hashes': expected_field_query(capsule),
        'identity_aliases': "SELECT id,module,name,model,res_id,noupdate FROM ir_model_data WHERE (model='hr.payroll.structure.type' AND res_id IN (1,2,3,4)) OR (model LIKE 'ir.actions.%' AND res_id=462) ORDER BY module,name,id",
        'action_462': "SELECT tableoid::regclass::text AS physical_table,id,type,md5(to_jsonb(t)::text) AS row_md5 FROM public.ir_actions t WHERE id=462 ORDER BY physical_table,id",
        'action_family': "WITH RECURSIVE family(oid) AS (SELECT 'public.ir_actions'::regclass::oid UNION ALL SELECT i.inhrelid FROM pg_inherits i JOIN family f ON i.inhparent=f.oid) SELECT n.nspname AS schema,c.relname AS table_name FROM family JOIN pg_class c USING(oid) JOIN pg_namespace n ON n.oid=c.relnamespace ORDER BY n.nspname,c.relname",
        'inbound_foreign_keys': "WITH RECURSIVE family(oid) AS (SELECT 'public.ir_actions'::regclass::oid UNION ALL SELECT i.inhrelid FROM pg_inherits i JOIN family f ON i.inhparent=f.oid) SELECT c.conname AS name,sn.nspname AS source_schema,sc.relname AS source_table,tn.nspname AS target_schema,tc.relname AS target_table,ARRAY(SELECT a.attname FROM unnest(c.conkey) WITH ORDINALITY k(attnum,ord) JOIN pg_attribute a ON a.attrelid=c.conrelid AND a.attnum=k.attnum ORDER BY k.ord) AS source_columns,ARRAY(SELECT a.attname FROM unnest(c.confkey) WITH ORDINALITY k(attnum,ord) JOIN pg_attribute a ON a.attrelid=c.confrelid AND a.attnum=k.attnum ORDER BY k.ord) AS target_columns,c.convalidated AS validated,c.condeferrable AS deferrable,c.confdeltype AS ondelete,pg_get_constraintdef(c.oid) AS definition FROM pg_constraint c JOIN pg_class sc ON sc.oid=c.conrelid JOIN pg_namespace sn ON sn.oid=sc.relnamespace JOIN pg_class tc ON tc.oid=c.confrelid JOIN pg_namespace tn ON tn.oid=tc.relnamespace WHERE c.contype='f' AND (c.confrelid='public.hr_payroll_structure_type'::regclass OR c.confrelid IN (SELECT oid FROM family)) ORDER BY sn.nspname,sc.relname,c.conname",
        'physical_columns': "SELECT c.relname AS table_name,a.attname AS column_name,format_type(a.atttypid,a.atttypmod) AS sql_type FROM pg_attribute a JOIN pg_class c ON c.oid=a.attrelid JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND c.relkind IN ('r','p') AND a.attnum>0 AND NOT a.attisdropped ORDER BY c.relname,a.attnum",
        'identity_relation_fields': "SELECT id,model,name,ttype,relation,store,related,company_dependent,to_jsonb(f)->>'model_field' AS model_field,to_jsonb(f)->>'relation_table' AS relation_table,to_jsonb(f)->>'column1' AS column1,to_jsonb(f)->>'column2' AS column2 FROM ir_model_fields f WHERE relation='hr.payroll.structure.type' OR relation LIKE 'ir.actions.%' OR ttype IN ('reference','many2one_reference') ORDER BY model,name",
        'relation_metadata': "SELECT r.name,m.model,r.module FROM ir_model_relation r LEFT JOIN ir_model m ON m.id=r.model ORDER BY r.name,r.model,r.module",
    })
    # The shared runner admits SELECT statements only. CTEs are nested in a
    # SELECT subquery rather than broadening its command admission policy.
    return {name: 'SELECT * FROM (' + query + ') readonly_cte' if query.startswith('WITH ') else query
        for name, query in statements.items()}


def reference_queries(metadata):
    """Count physical FK and visible reference candidates, never rewrite them."""
    statements, paths, unresolved = {}, [], []
    columns = {(row['table_name'], row['column_name']): row['sql_type'] for row in metadata['physical_columns']}
    for index, fk in enumerate(metadata['inbound_foreign_keys']):
        entry = dict(fk, path_kind='physical-foreign-key')
        if fk['source_schema'] != 'public' or fk['target_schema'] != 'public' or fk['target_columns'] != ['id'] or len(fk['source_columns']) != 1:
            unresolved.append(dict(entry, blocker='unreviewed-schema-or-composite-reference'))
            continue
        table, field = fk['source_table'], fk['source_columns'][0]
        ids = '(1,2,3,4)' if fk['target_table'] == 'hr_payroll_structure_type' else '(462)'
        key = 'path:fk:' + str(index)
        identity = 'jsonb_build_array(t.' + identifier(field) + (',t.id)' if (table, 'id') in columns else ')')
        statements[key] = 'SELECT count(*) AS rows,md5(coalesce(string_agg((' + identity + ')::text,E\'\\n\' ORDER BY (' + identity + ')::text),\'\')) AS reference_ids_md5 FROM public.' + identifier(table) + ' t WHERE ' + identifier(field) + ' IN ' + ids
        entry['owner_record_ids_bound'] = (table, 'id') in columns
        paths.append(dict(entry, observation=key))
    for index, field in enumerate(metadata['identity_relation_fields']):
        if not field['store']:
            continue
        table, name = field['model'].replace('.', '_'), field['name']
        entry = dict(field, guessed_table=table, table_mapping_certified=False)
        if (table, name) not in columns:
            unresolved.append(dict(entry, blocker='stored-field-has-no-proven-physical-model-table-binding'))
            continue
        if field['ttype'] == 'reference':
            sql_type = columns[table, name]
            if sql_type not in ('text', 'character varying'):
                unresolved.append(dict(entry, blocker='reference-storage-not-reviewed-text'))
                continue
            predicate = identifier(name) + " ~ '^(hr[.]payroll[.]structure[.]type,[1-4]|ir[.]actions[.][a-z_]+,462)$'"
        elif field['ttype'] == 'many2one_reference':
            if columns[table, name] not in ('integer', 'bigint'):
                unresolved.append(dict(entry, blocker='polymorphic-integer-storage-not-reviewed'))
                continue
            predicate = identifier(name) + ' IN (1,2,3,4,462)'
            entry['referent_model_not_certified'] = True
        else:
            if field['ttype'] == 'many2many':
                unresolved.append(dict(entry, blocker='many2many-runtime-table-column-binding-required'))
            elif not any(fk['source_table'] == table and fk['source_columns'] == [name] for fk in metadata['inbound_foreign_keys']):
                unresolved.append(dict(entry, blocker='stored-relation-without-reviewed-physical-foreign-key'))
            continue
        key = 'path:polymorphic:' + str(index)
        identity = 'jsonb_build_array(t.' + identifier(name) + (',t.id)' if (table, 'id') in columns else ')')
        statements[key] = 'SELECT count(*) AS rows,md5(coalesce(string_agg((' + identity + ')::text,E\'\\n\' ORDER BY (' + identity + ')::text),\'\')) AS reference_ids_md5 FROM public.' + identifier(table) + ' t WHERE ' + predicate
        paths.append(dict(entry, path_kind='polymorphic-candidate', observation=key))
    return statements, paths, unresolved


def field_classification(name):
    if name in AUDIT_FIELDS:
        return 'original-audit-identity-not-adopted'
    if name in POLICY_FIELDS:
        return 'policy-or-default-difference-requires-original-adoption'
    if name in IDENTITY_FIELDS:
        return 'business-identity-difference-not-authorized'
    return 'unreviewed-original-field-difference'


def plan(capsule, source, target, *, paths, unresolved):
    expected = {(row['id'], row['field']): row for row in source['expected_type_value_hashes']}
    actual_source = {(row['id'], row['field']): row for row in source['type_value_hashes']}
    actual_target = {(row['id'], row['field']): row for row in target['type_value_hashes']}
    gate.require(expected == actual_source, 'original-four-types-no-longer-match-sealed-capsule')
    aliases = lambda metadata: {(row['module'], row['name']): row for row in metadata['identity_aliases']}
    old_aliases, new_aliases = aliases(source), aliases(target)
    types = []
    blockers = {'serialized-runtime-and-integer-embedded-reference-contract-not-certified',
                'original-security-and-model-metadata-not-adopted', 'original-report-462-identity-not-adopted'}
    for ident, name in zip(TYPE_IDS, TYPE_ALIASES):
        key = ('hr_contract', name)
        before, after = old_aliases.get(key), new_aliases.get(key)
        gate.require(before and before['model'] == TYPE_MODEL and before['res_id'] == ident and before['noupdate'] is True, 'original-official-type-alias-contract-drift')
        canonical = bool(after and all(before[field] == after[field] for field in ('module', 'name', 'model', 'res_id', 'noupdate')))
        alias_pk_equal = bool(after and before['id'] == after['id'])
        comparisons = []
        for _, field in sorted(key for key in expected if key[0] == ident):
            left, right = expected[ident, field], actual_target.get((ident, field))
            equal = right == left
            comparisons.append({'field': field, 'equal': equal, 'source': left, 'target': right,
                'classification': 'exact-original-value-hash' if equal else 'missing-original-field' if right is None else field_classification(field),
                'write_authorized': False})
        extras = [row for key, row in actual_target.items() if key[0] == ident and key not in expected]
        business_equal = all(row['equal'] for row in comparisons if row['field'] in IDENTITY_FIELDS)
        if not canonical:
            blockers.add('official-type-canonical-alias-or-noupdate-differs')
        if not alias_pk_equal:
            blockers.add('original-official-type-xmlid-metadata-primary-key-not-adopted')
        if not business_equal:
            blockers.add('official-type-business-identity-not-equivalent')
        if any(not row['equal'] for row in comparisons):
            blockers.add('original-official-type-field-values-not-adopted')
        types.append({'original_id': ident, 'canonical_xmlid': '.'.join(key), 'source_alias': before, 'target_alias': after,
            'same_canonical_alias_model_res_id_noupdate': canonical, 'original_xmlid_metadata_pk_equal': alias_pk_equal,
            'name_and_country_value_hashes_equal': business_equal, 'field_comparisons': comparisons,
            'target_only_fields': extras, 'shared_official_seed_candidate': canonical,
            'relocation_authorized': False, 'overwrite_authorized': False, 'adoption_complete': False})
    report = old_aliases.get(('hr_payroll', 'action_report_payslip'))
    gate.require(report and report['model'] == 'ir.actions.report' and report['res_id'] == 462, 'original-report-action-alias-drift')
    source_matches = all(source['source_hash:' + table][0]['rows_sha256'] == values['rows_sha256'] for table, values in capsule['tables'].items())
    gate.require(source_matches, 'original-120-masters-or-relations-changed')
    if any(unresolved.values()):
        blockers.add('declared-reference-bindings-not-exhaustively-certified')
    if any(not path.get('owner_record_ids_bound', True) and path['count'][0]['rows']
           for side in paths.values() for path in side):
        blockers.add('nonempty-reference-table-owner-identity-not-bound')
    return {'schema': 1, 'read_only': True, 'orm_loaded': False, 'database_writes': False,
        'source_master_count': sum(values['row_count'] for name, values in capsule['tables'].items() if name in gate.TABLES),
        'source_rule_count': capsule['tables']['hr_salary_rule']['row_count'], 'source_configuration_hashes_equal': True,
        'types': types, 'original_report_alias': report, 'source_action_462': source['action_462'],
        'target_action_462': target['action_462'], 'source_action_aliases': [row for row in source['identity_aliases'] if row['model'].startswith('ir.actions.')],
        'target_action_aliases': [row for row in target['identity_aliases'] if row['model'].startswith('ir.actions.')],
        'declared_paths': paths, 'unresolved_declared_bindings': unresolved,
        'action_strategy': {'existing_target_mutation_authorized': False, 'candidate': 'reserve-original-action-identity-in-new-cold-bootstrap-before-conflicting-seeds',
            'selected_relocation_id': None, 'sequence_reservation_authorized': False,
            'requires_complete_dynamic_and_serialized_reference_contract': True, 'original_action_462_must_keep_id_and_model': True},
        'all_runtime_or_serialized_paths_certified': False, 'all_model_table_bindings_certified': False,
        'adoption_ready': False, 'import_authorized': False, 'blockers': sorted(blockers)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capsule', type=Path, required=True)
    parser.add_argument('--expected-capsule-sha256', required=True)
    parser.add_argument('--target-database', required=True)
    parser.add_argument('--output-directory', type=Path, required=True)
    args = parser.parse_args()
    gate.require(stat.S_IMODE(args.capsule.stat().st_mode) == 0o600 and sha(args.capsule) == args.expected_capsule_sha256, 'private-sealed-source-capsule-required')
    capsule = json.loads(args.capsule.read_text())
    gate.capsule_rows(capsule)
    gate.require(args.target_database.startswith('COMMUNITY_PAYROLL_API_ORIGINAL_BOOTSTRAP_'), 'accepted-private-cold-target-required')
    gate.require(capsule['database'].startswith('MANAGEMENT_QA_CERRO_PAYROLL_API_'), 'private-native-source-required')
    output = args.output_directory.resolve()
    gate.require(output.is_relative_to(Path('/opt/steps-validation')) and not output.exists(), 'new-private-evidence-directory-required')
    observations, path_plans, missing_bindings = {}, {}, {}
    for label, database, is_source in (('source', capsule['database'], True), ('target', args.target_database, False)):
        queries = metadata_queries(capsule, source=is_source)
        discovery = gate.run_snapshot(database, queries)
        counted, paths, missing = reference_queries(discovery)
        first = gate.run_snapshot(database, dict(queries, **counted))
        second = gate.run_snapshot(database, dict(queries, **counted))
        gate.require(all(first[key] == value for key, value in discovery.items()), 'catalog-changed-during-reference-discovery')
        gate.require(first == second, 'readonly-identity-reference-snapshots-drifted')
        observations[label] = {'database': database, 'before': first, 'after': second,
            'two_readonly_snapshots_equal': True, 'discovery_metadata_unchanged': True}
        path_plans[label] = [dict(path, count=first[path['observation']]) for path in paths]
        missing_bindings[label] = missing
    report = plan(capsule, observations['source']['before'], observations['target']['before'], paths=path_plans, unresolved=missing_bindings)
    report['original_security_plan'] = security.preservation_plan(observations['source']['before'], observations['target']['before'])
    report['blockers'] = sorted(set(report['blockers']) | set(report['original_security_plan']['blockers']))
    report.update(capsule_sha256=args.expected_capsule_sha256, tool_sha256=sha(__file__), gate_tool_sha256=sha(gate.__file__),
        observations=observations, source_database=capsule['database'], target_database=args.target_database)
    output.mkdir(mode=0o700)
    for name, raw in (('identity-adoption-plan.json', json.dumps(report, indent=2).encode()), ('auditor.py', Path(__file__).read_bytes())):
        with os.fdopen(os.open(output / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'wb') as stream:
            stream.write(raw)
    print(json.dumps({'evidence': str(output / 'identity-adoption-plan.json'), 'sha256': sha(output / 'identity-adoption-plan.json'),
        'shared_official_seed_candidates': sum(row['shared_official_seed_candidate'] for row in report['types']),
        'blockers': report['blockers'], 'adoption_ready': False, 'database_writes': False}))


if __name__ == '__main__':
    main()
