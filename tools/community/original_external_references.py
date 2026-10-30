"""Executable readonly closure of ORIGINAL payroll physical references.

Registry bindings are explicit provenance, not model-name table guesses.
Capture full owner keys, FK/M2M/reference/JSON edges and alias PK occupants;
unclassified serialized storage remains a blocker. Never reserve, renumber,
write SQL, import masters, evaluate formulas or start an Odoo registry.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess

import payroll_configuration_adoption_preflight as gate
from original_external_references_dump import prove_original_identity


IDENT = re.compile(r'[a-z_][a-z0-9_]*\Z')
INTEGER_TYPES = ('smallint', 'integer', 'bigint')
TEXT_TYPES = ('text', 'character varying')
CAPSULE_SHA256 = '14b18ced97032ec27c306ed4c71c46f0c3d56e324d0eace4f0c8f2c86544e140'
TYPE_ALIASES = ('structure_type_employee', 'structure_type_worker',
    'structure_type_employee_cp200_pfi', 'structure_type_employee_cp200')
# Reviewed SELECT-only launcher 0c064cc7. Advancing this policy requires a
# separate review; an arbitrary JSON claim is not a registry-runtime proof.
RUNTIME_SOURCE_SHA256 = {
    'original_external_references_runtime.py': (
        '8c8b963a0de148468a50ce02c6f3806b5ece737d7be5a9ef7f8d755e6be50eac',  # 0c064cc7 Community
        '4162684ed5f1932f8765285e829a8a8be8b68fc09c755c40db4fc1026c479c2e',  # 2ae00751 official CLI
    ),
    'original_external_references_readonly_bootstrap.py': ('60a7863ad1313648a68ebb938cd524216af1eb9d8bf8698b9a4ead0e215b68b2',),
}
SEQUENCE_METHOD_SHA256 = '6c41a6d4a995835a69a550420fbefb0987845008d8033035c96fea0670e5e000'
SEQUENCE_SELECT_SHA256 = '641394a53615d5d518b5e6f7c8ba4f867036d3ba66b848be7ce5789c001dc52b'
REGISTRY_SOURCE_SHA256 = {'community': '20a64452e404254f6cc067f1e06753ac9f8723239d465ace96f797719beb1ffb',
    'cerro-reference': '9db45ba41656e998b4720003b20a53f3eb115459815755e65096c97dae86631f'}
SERIALIZED_CONFIG = {
    'ir_act_window': ('domain', 'context'), 'ir_filters': ('domain', 'context', 'sort'),
    'ir_ui_view': ('arch_db',), 'ir_act_server': ('code',),
    'ir_default': ('json_value',), 'ir_act_client': ('params_store',),
}


def require(condition, code):
    if not condition:
        raise ValueError(code)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def ident(value):
    require(isinstance(value, str) and IDENT.fullmatch(value), 'unreviewed-physical-identifier')
    return '"' + value + '"'


def literal(value):
    require(isinstance(value, str) and '\x00' not in value, 'invalid-reference-literal')
    return "'" + value.replace("'", "''") + "'"


def ids(values):
    require(values and all(type(value) is int and 0 < value < 2**31 for value in values), 'invalid-reference-id-scope')
    return '(' + ','.join(str(value) for value in sorted(set(values))) + ')'


def run_snapshot(database, statements):
    require(re.fullmatch(r'(?:COMMUNITY_PAYROLL_API_|MANAGEMENT_QA_CERRO_PAYROLL_API_)[A-Za-z0-9_]+', database),
        'private-reference-database-required')
    commands = ['BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY;']
    for name, query in statements.items():
        require(query.lstrip().upper().startswith('SELECT '), 'select-only-reference-query')
        commands.append('SELECT jsonb_build_object(\'section\',' + literal(name)
            + ",'rows',coalesce(jsonb_agg(t),'[]'::jsonb)) FROM (" + query + ') t;')
    commands.append('ROLLBACK;')
    command = ['sudo', '-u', 'postgres', 'env', '-u', 'PGPASSWORD', '-u', 'PGSERVICE', '-u', 'PGSERVICEFILE',
        'PGHOST=/var/run/postgresql', 'PGPASSFILE=/opt/steps-validation/no-such-readonly-passfile',
        'PGOPTIONS=-c default_transaction_read_only=on', 'psql', '-XAtq', '-v', 'ON_ERROR_STOP=1', '-d', database]
    result = subprocess.run(command, input='\n'.join(commands), capture_output=True, text=True)
    require(result.returncode == 0, 'readonly-reference-query-failed-raw-diagnostics-withheld')
    values = [json.loads(line) for line in result.stdout.splitlines() if line]
    sections = {row['section']: row['rows'] for row in values}
    require(len(sections) == len(statements) == len(values), 'incomplete-reference-snapshot')
    if 'transaction' in statements:
        require(sections['transaction'] == [{'mode': 'on'}], 'reference-transaction-not-readonly')
    return sections


def scope_from_capsule(capsule):
    rows = gate.capsule_rows(capsule)
    require(sum(len(rows[table]) for table in gate.TABLES) == 120 and len(rows['hr_salary_rule']) == 71,
        'exact-original-120-masters-71-rules-required')
    scope = {model: {'table': table, 'ids': sorted(row['id'] for row in rows[table]), 'incoming_scope': True}
        for table, model in gate.TABLES.items()}
    fields = {(row['model'], row['name']): row for row in capsule['field_metadata']}
    for name, reference in capsule['external_references'].items():
        table, field = name.split('.', 1)
        require(table in gate.TABLES, 'unknown-original-reference-owner')
        meta = fields.get((gate.TABLES[table], field))
        require(meta and meta['type'] == 'many2one' and meta['relation'], 'original-reference-comodel-not-declared')
        model = meta['relation']
        previous = scope.setdefault(model, {'table': reference['target'], 'ids': [], 'incoming_scope': model == 'ir.actions.report'})
        require(previous['table'] == reference['target'], 'original-comodel-physical-target-conflict')
        previous['ids'] = sorted(set(previous['ids']) | set(reference['ids']))
        if reference.get('company_dependent'):
            company = scope.setdefault('res.company', {'table': 'res_company', 'ids': [], 'incoming_scope': False})
            company['ids'] = sorted(set(company['ids']) | set(reference['company_ids']))
    scope = {model: row for model, row in scope.items() if row['ids']}
    for row in scope.values():
        ident(row['table']); ids(row['ids'])
    require(scope.get('ir.actions.report', {}).get('ids') == [462], 'original-report-462-reference-required')
    return scope


def registry_models(proof):
    require(proof['schema'] == 1 and proof['read_only'] is True
        and all(proof[flag] is False for flag in ('orm_loaded_by_payload', 'orm_records_accessed',
            'source_bodies_read', 'callables_executed', 'database_writes', 'adoption_authorized')),
        'readonly-registry-metadata-proof-required')
    rows = proof['models']
    result = {row['model']: row for row in rows}
    require(len(result) == len(rows), 'duplicate-registry-model-binding')
    for row in rows:
        require(isinstance(row['fields'], list) and len({field['name'] for field in row['fields']}) == len(row['fields']),
            'duplicate-registry-field-binding')
    return result


def runtime_contract(receipt, registry, accepted, before, after):
    """Admission of the reviewed connection policy; no callable execution."""
    require(receipt['schema'] == 1 and receipt['database'] == registry['database'] == accepted['database']
        and receipt['mode'] == accepted['mode'], 'runtime-database-or-mode-differs')
    for flag in ('all_tables_and_sequences_exact', 'all_infrastructure_sequences_also_exact',
            'external_network_disabled', 'postgres_unix_socket', 'odoo_pool_readonly_before_connect',
            'read_only_before_registry_startup'):
        require(receipt[flag] is True, 'readonly-runtime-guard-not-proven:' + flag)
    require(receipt['adoption_authorized'] is False and receipt['upgraded'] is False, 'runtime-mutation-or-adoption-claim')
    require(before == after and isinstance(before, dict) and len(before) == receipt['public_snapshots_count'] > 0,
        'runtime-public-tables-or-sequences-changed')
    reader = receipt['readonly_sequence_reader']
    require(reader == registry['readonly_sequence_reader'], 'runtime-sequence-reader-proof-differs')
    require(reader['original_get_sequences_sha256'] == SEQUENCE_METHOD_SHA256
        and reader['select_only_sql_sha256'] == SEQUENCE_SELECT_SHA256
        and reader['original_registry_source_sha256'] == REGISTRY_SOURCE_SHA256[accepted['mode']]
        and reader['cache_keys'] == ['default', 'assets', 'templates', 'routing', 'groups'],
        'unreviewed-sequence-reader-policy')
    for flag in ('cursor_readonly_unchanged', 'setup_signaling_unchanged', 'signal_changes_unchanged', 'nextval_unchanged'):
        require(reader[flag] is True, 'sequence-write-guard-was-altered')
    require(reader['installed_sources_modified'] is False, 'installed-runtime-source-was-modified')
    require(reader['calls'] and registry['readonly_cursor_proof'], 'actual-readonly-cursor-witness-required')
    for row in reader['calls'] + registry['readonly_cursor_proof']:
        require(row['database'] == registry['database'] and row['odoo_cursor_readonly'] is True
            and row['transaction_read_only'] == 'on', 'runtime-cursor-was-not-readonly')
    require(all(row['pg_is_in_recovery'] is False for row in reader['calls']), 'runtime-primary-local-sequence-source-not-proven')
    required = {'base_registry_signaling'} | {'base_cache_signaling_' + key for key in reader['cache_keys']}
    require(required <= set(before), 'runtime-signaling-counters-not-captured')
    return {'all_tables_and_sequences_exact': True, 'public_snapshots_count': len(before),
        'readonly_from_before_first_odoo_connection': True, 'sequence_reader_policy_reviewed': True,
        'database_writes': False, 'upgraded': False, 'adoption_authorized': False}


def verify_runtime_proof(path, registry_path, registry, acceptance_path, accepted):
    """Bind the runtime receipt, exact helper bytes and all snapshot files."""
    receipt = json.loads(path.read_text())
    require(path.name == 'passed.json' and path.parent == registry_path.parent and registry_path.name == 'registry.json',
        'runtime-receipt-and-registry-location-differs')
    before_path, after_path = (path.parent / name for name in ('business-before.json', 'business-after.json'))
    require(receipt['registry_json_sha256'] == sha(registry_path)
        and receipt['acceptance_sha256'] == sha(acceptance_path)
        and receipt['payload_sha256'] == registry['tool_sha256']
        and receipt['source_packet_sha256'] == receipt['source_files_json_sha256'] == accepted['source_files_sha256'],
        'runtime-provenance-differs')
    require(receipt['business_before_sha256'] == sha(before_path)
        and receipt['business_after_sha256'] == sha(after_path)
        and before_path.read_bytes() == after_path.read_bytes(), 'runtime-snapshot-file-changed')
    source = path.parent.parent / 'source'
    observed = {name: sha(source / name) for name in RUNTIME_SOURCE_SHA256}
    for name, expected in RUNTIME_SOURCE_SHA256.items():
        require(observed[name] in expected, 'runtime-helper-differs-from-reviewed-policy')
    require(receipt['runner_sha256'] == observed['original_external_references_runtime.py']
        and receipt['readonly_bootstrap_sha256'] == observed['original_external_references_readonly_bootstrap.py'],
        'runtime-helper-receipt-differs')
    official_cli = receipt['runner_sha256'] == RUNTIME_SOURCE_SHA256['original_external_references_runtime.py'][1]
    require(accepted['mode'] != 'cerro-reference' or official_cli, 'native-runtime-must-not-use-upgrade-finalizer')
    if official_cli:
        require(receipt['entry_kind'] == 'official_cli_no_upgrade' and receipt['upgrade_preservation_finalizer_executed'] is False
            and re.fullmatch('[0-9a-f]{64}', receipt['entry_sha256']), 'official-no-upgrade-entry-not-proven')
    result = runtime_contract(receipt, registry, accepted,
        json.loads(before_path.read_text()), json.loads(after_path.read_text()))
    result.update(receipt_sha256=sha(path), registry_json_sha256=sha(registry_path),
        before_sha256=sha(before_path), after_sha256=sha(after_path), executed_source_hashes=observed)
    return result


def original_aliases(capsule, identity_before):
    """88 source aliases and report462; do not reserve 3 adapter aliases."""
    rows = identity_before['original_xmlids']
    index = {(row['module'], row['name']): row for row in rows}
    require(len(index) == len(rows) and all('noupdate' in row for row in rows), 'complete-original-xmlid-snapshot-required')
    original, reference = [], []
    keys = ('id', 'module', 'name', 'model', 'res_id', 'noupdate')
    for row in capsule['xmlids']:
        prior = index.get((row['module'], row['name']))
        if prior is None:
            reference.append(row)
        else:
            require(all(prior[key] == row[key] for key in keys), 'capsule-original-alias-differs-from-preupgrade-identity')
            original.append({key: prior[key] for key in keys})
    require(len(original) == 88 and len(reference) == 3, 'exact-88-original-plus-3-reference-aliases-required')
    for number, name in enumerate(TYPE_ALIASES, 1):
        row = index.get(('hr_contract', name))
        require(row and row['model'] == 'hr.payroll.structure.type' and row['res_id'] == number
            and row['noupdate'] is True, 'canonical-original-type-alias-binding-differs')
    report = index.get(('hr_payroll', 'action_report_payslip'))
    require(report and report['model'] == 'ir.actions.report' and report['res_id'] == 462,
        'original-report462-alias-not-proven')
    return original + [{key: report[key] for key in keys}], reference


def catalog_queries(scope, aliases):
    """Public catalogues/technical metadata, never formula/text bodies."""
    selected = ids([row['id'] for row in aliases])
    names = '(' + ','.join('(' + literal(row['module']) + ',' + literal(row['name']) + ')' for row in aliases) + ')'
    result = {
        'transaction': "SELECT current_setting('transaction_read_only') AS mode",
        'database': 'SELECT current_database() AS database',
        'modules': "SELECT name,latest_version,license,state FROM ir_module_module WHERE state='installed' ORDER BY name",
        'pending': "SELECT name,state FROM ir_module_module WHERE state IN ('to install','to upgrade','to remove') ORDER BY name",
        'tables': "SELECT c.oid,n.nspname AS schema,c.relname AS name,c.relkind AS kind FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND c.relkind IN ('r','p','v','m') ORDER BY c.relname",
        'columns': "SELECT c.relname AS table_name,a.attname AS name,format_type(a.atttypid,a.atttypmod) AS sql_type,a.attnotnull AS not_null FROM pg_attribute a JOIN pg_class c ON c.oid=a.attrelid JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND c.relkind IN ('r','p','v','m') AND a.attnum>0 AND NOT a.attisdropped ORDER BY c.relname,a.attnum",
        'keys': "SELECT c.relname AS table_name,i.relname AS name,x.indisprimary AS primary_key,ARRAY(SELECT a.attname FROM unnest(x.indkey) WITH ORDINALITY k(attnum,ord) JOIN pg_attribute a ON a.attrelid=x.indrelid AND a.attnum=k.attnum WHERE k.ord<=x.indnkeyatts ORDER BY k.ord) AS columns FROM pg_index x JOIN pg_class c ON c.oid=x.indrelid JOIN pg_class i ON i.oid=x.indexrelid JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND x.indisunique AND x.indisvalid AND x.indpred IS NULL AND x.indexprs IS NULL ORDER BY c.relname,x.indisprimary DESC,i.relname",
        'foreign_keys': "SELECT x.conname AS name,sn.nspname AS source_schema,s.relname AS source_table,tn.nspname AS target_schema,t.relname AS target_table,x.convalidated AS validated,x.confdeltype AS ondelete,ARRAY(SELECT a.attname FROM unnest(x.conkey) WITH ORDINALITY k(attnum,ord) JOIN pg_attribute a ON a.attrelid=x.conrelid AND a.attnum=k.attnum ORDER BY k.ord) AS source_columns,ARRAY(SELECT a.attname FROM unnest(x.confkey) WITH ORDINALITY k(attnum,ord) JOIN pg_attribute a ON a.attrelid=x.confrelid AND a.attnum=k.attnum ORDER BY k.ord) AS target_columns FROM pg_constraint x JOIN pg_class s ON s.oid=x.conrelid JOIN pg_namespace sn ON sn.oid=s.relnamespace JOIN pg_class t ON t.oid=x.confrelid JOIN pg_namespace tn ON tn.oid=t.relnamespace WHERE x.contype='f' AND sn.nspname='public' ORDER BY s.relname,x.conname",
        'fields': "SELECT id,model,name,ttype,relation,store,related,company_dependent FROM ir_model_fields WHERE ttype IN ('many2one','one2many','many2many','reference','many2one_reference','json','properties','properties_definition') OR company_dependent ORDER BY model,name",
        'alias_occupants': 'SELECT id,module,name,model,res_id,noupdate FROM ir_model_data WHERE id IN ' + selected + ' OR (module,name) IN ' + names + ' ORDER BY id',
        'action_462': "SELECT tableoid::regclass::text AS physical_table,id,type,encode(sha256(convert_to(to_jsonb(t)::text,'UTF8')),'hex') AS row_sha256 FROM public.ir_actions t WHERE id=462 ORDER BY physical_table,id",
        'action_family': "SELECT c.relname AS table_name FROM pg_class c WHERE c.oid IN (WITH RECURSIVE family(oid) AS (SELECT 'public.ir_actions'::regclass::oid UNION ALL SELECT i.inhrelid FROM pg_inherits i JOIN family f ON i.inhparent=f.oid) SELECT oid FROM family) ORDER BY c.relname",
    }
    for model, selected in scope.items():
        result['target-occupants:' + model] = ('SELECT id,tableoid::regclass::text AS physical_table,'
            "encode(sha256(convert_to(to_jsonb(t)::text,'UTF8')),'hex') AS row_sha256 FROM public."
            + ident(selected['table']) + ' t WHERE id IN ' + ids(selected['ids']) + ' ORDER BY id,physical_table')
        result['target-aliases:' + model] = ('SELECT id,module,name,model,res_id,noupdate FROM ir_model_data WHERE model='
            + literal(model) + ' AND res_id IN ' + ids(selected['ids']) + ' ORDER BY id')
        if model in gate.TABLES.values():
            result['original-master-hash:' + selected['table']] = (
                "SELECT encode(sha256(convert_to(coalesce(string_agg(to_jsonb(t)::text,E'\\n' ORDER BY id),''),'UTF8')),'hex') AS rows_sha256 FROM public."
                + ident(selected['table']) + ' t WHERE id IN ' + ids(selected['ids']))
    return result


def action_reference_scope(catalog, registry, scope):
    result = {model: dict(row) for model, row in scope.items()}
    family = {row['table_name'] for row in catalog['action_family']}
    mapped = set()
    for model, binding in registry_models(registry).items():
        if model.startswith('ir.actions.') and not binding['abstract'] and binding['table'] in family:
            mapped.add(binding['table'])
            result.setdefault(model, {'table': binding['table'], 'ids': [462],
                'original_expected': model == 'ir.actions.actions', 'incoming_scope': True})
    require(mapped == family, 'action-inheritance-family-model-bindings-incomplete')
    return result


def _owner(table, catalog):
    columns = {row['name']: row for row in catalog['columns'] if row['table_name'] == table}
    keys = [row for row in catalog['keys'] if row['table_name'] == table and row['columns']
        and all(name in columns and columns[name]['not_null'] for name in row['columns'])]
    keys.sort(key=lambda row: (not row['primary_key'], len(row['columns']), row['name']))
    if not keys:
        return None
    key = keys[0]
    return {'constraint': key['name'], 'columns': key['columns'], 'primary_key': key['primary_key'],
        'physical_table_system_column': 'tableoid',
        'component_foreign_keys': [row for row in catalog['foreign_keys'] if row['source_table'] == table
            and set(row['source_columns']) <= set(key['columns'])]}


def _owner_sql(owner):
    if owner is None:
        return "'null'::jsonb"
    # PostgreSQL inheritance does not make a parent's PK globally unique over
    # child tables. Preserve the row's real tableoid as part of every owner.
    return "jsonb_build_object('_physical_table',t.tableoid::regclass::text," + ','.join(
        literal(name) + ',t.' + ident(name) for name in owner['columns']) + ')'


def _rows(table, owner, target_model, target_sql, predicate, *, company_sql='NULL::integer'):
    return ('SELECT ' + _owner_sql(owner) + ' AS owner_pk,' + (literal(target_model) if target_model else 'NULL::text') + ' AS target_model,'
        + target_sql + ' AS target_id,' + company_sql + ' AS company_id FROM public.' + ident(table)
        + ' t WHERE ' + predicate + ' ORDER BY owner_pk,target_id,company_id')


def compile_paths(catalog, registry, scope):
    """Compile executable SELECTs only for registry/catalog-proven storage."""
    models = registry_models(registry)
    tables = {row['name']: row for row in catalog['tables']}
    columns = {(row['table_name'], row['name']): row for row in catalog['columns']}
    fields = {(row['model'], row['name']): row for row in catalog['fields']}
    queries, paths, blockers, seen = {}, [], [], set()
    def scoped_owner(model):
        return model in gate.TABLES.values() or model.startswith('ir.actions.') and model in scope
    for model, selected in scope.items():
        binding = models.get(model)
        require(binding and not binding['abstract'] and binding['table'] == selected['table'], 'scope-model-table-binding-not-proven')
        require(selected['table'] in tables and tables[selected['table']]['kind'] in ('r', 'p'), 'scope-target-is-not-a-physical-table')
    for row in catalog['fields']:
        if not row['store'] or not (row['relation'] in scope or scoped_owner(row['model'])
                or row['ttype'] in ('reference', 'many2one_reference', 'json', 'properties', 'properties_definition')):
            continue
        binding = models.get(row['model'])
        loaded = next((field for field in binding['fields'] if field['name'] == row['name']), None) if binding else None
        if loaded is None:
            blockers.append({'code': 'stored-sql-reference-metadata-not-in-loaded-registry',
                'model': row['model'], 'field': row['name'], 'metadata_id': row['id']})

    def add(kind, table, field, target_model, target_sql, predicate, **extra):
        key = (table, field, target_model, kind)
        if key in seen:
            return
        seen.add(key)
        owner = _owner(table, catalog)
        if owner is None:
            blockers.append({'code': 'owner-primary-or-nonnull-unique-key-not-proven', 'table': table, 'field': field})
        name = 'edge:' + str(len(paths))
        company_sql = extra.pop('company_sql', 'NULL::integer')
        target_table = extra.pop('target_table', scope.get(target_model, {}).get('table'))
        queries[name] = _rows(table, owner, target_model, target_sql, predicate, company_sql=company_sql)
        paths.append(dict(kind=kind, table=table, field=field, target_model=target_model,
            target_table=target_table, owner_key=owner, observation=name, **extra))

    # Every outgoing physical FK from the 120 original owners and action462 is
    # captured, including endpoints not enumerated in the older capsule (e.g.
    # report model/paperformat). Scope does not expand adoption to those masters.
    owners = {row['table']: model for model, row in scope.items() if scoped_owner(model)}
    for fk in catalog['foreign_keys']:
        if fk['source_table'] not in owners:
            continue
        model = owners[fk['source_table']]
        if (fk['source_schema'], fk['target_schema'], fk['target_columns']) != ('public', 'public', ['id']) or len(fk['source_columns']) != 1 or not fk['validated']:
            blockers.append({'code': 'original-owner-outbound-fk-not-proven', 'foreign_key': fk})
            continue
        table, column = fk['source_table'], fk['source_columns'][0]
        declared = next((row for row in models[model]['fields'] if row['name'] == column), None)
        target = declared.get('comodel') if declared else None
        if target not in models or models[target]['table'] != fk['target_table']:
            choices = [name for name, row in models.items() if not row['abstract'] and row['table'] == fk['target_table']]
            target = choices[0] if len(choices) == 1 else None
        if target is None:
            blockers.append({'code': 'outbound-fk-target-model-ambiguous', 'foreign_key': fk})
        add('outbound-original-fk', table, column, target, 't.' + ident(column),
            't.id IN ' + ids(scope[model]['ids']) + ' AND t.' + ident(column) + ' IS NOT NULL',
            target_table=fk['target_table'], owner_model=model, constraint_enforced=True,
            foreign_key=fk['name'], semantic_binding_proven=target is not None)

    table_targets = {}
    for model, row in scope.items():
        if row.get('incoming_scope', True):
            table_targets.setdefault(row['table'], []).append(model)
    for fk in catalog['foreign_keys']:
        if fk['target_table'] not in table_targets:
            continue
        if (fk['source_schema'], fk['target_schema'], fk['target_columns']) != ('public', 'public', ['id']) or len(fk['source_columns']) != 1 or not fk['validated']:
            blockers.append({'code': 'unreviewed-or-unvalidated-foreign-key', 'foreign_key': fk})
            continue
        model_list = table_targets[fk['target_table']]
        require(len(model_list) == 1, 'ambiguous-scope-physical-target')
        model, table, field = model_list[0], fk['source_table'], fk['source_columns'][0]
        require((table, field) in columns, 'foreign-key-column-not-captured')
        add('physical-fk', table, field, model, 't.' + ident(field),
            't.' + ident(field) + ' IN ' + ids(scope[model]['ids']), foreign_key=fk['name'], constraint_enforced=True)

    for model_name, binding in sorted(models.items()):
        table = binding['table']
        if binding['abstract'] or table not in tables:
            continue
        for field in binding['fields']:
            name, kind, target = field['name'], field['type'], field['comodel']
            original_owner = scoped_owner(model_name)
            if original_owner and field['store'] and kind in ('many2one', 'one2many', 'many2many') and target not in models:
                blockers.append({'code': 'outbound-original-comodel-not-in-loaded-registry', 'model': model_name, 'field': name})
                continue
            incoming = target in scope and scope[target].get('incoming_scope', True)
            relevant = incoming or original_owner and target in models or kind in ('reference', 'many2one_reference')
            if not field['store'] or not relevant:
                continue
            if tables[table]['kind'] not in ('r', 'p'):
                blockers.append({'code': 'reference-owner-is-a-view-not-stored-history', 'model': model_name, 'field': name})
                continue
            meta = fields.get((model_name, name))
            if not meta or (meta['ttype'], meta['store'], bool(meta['company_dependent'])) != (kind, field['store'], field['company_dependent']) or (
                    kind in ('many2one', 'one2many', 'many2many') and meta['relation'] != field['comodel']):
                blockers.append({'code': 'registry-sql-field-contract-differs', 'model': model_name, 'field': name})
                continue
            if original_owner and target in models:
                actual_target_table = models[target]['table']
                if actual_target_table not in tables or tables[actual_target_table]['kind'] not in ('r', 'p'):
                    blockers.append({'code': 'outbound-reference-target-is-not-physical-storage', 'model': model_name, 'field': name})
                    continue
            if kind == 'many2many':
                rel, left, right = field['relation_table'], field['column1'], field['column2']
                owner_target = binding['table']
                target_table = models[target]['table']
                actual = lambda col, destination: any(fk['source_table'] == rel and fk['source_columns'] == [col]
                    and fk['target_schema'] == 'public' and fk['target_table'] == destination
                    and fk['target_columns'] == ['id'] and fk['validated'] for fk in catalog['foreign_keys'])
                if rel not in tables or not actual(left, owner_target) or not actual(right, target_table):
                    blockers.append({'code': 'many2many-actual-table-column-fks-not-proven', 'model': model_name, 'field': name})
                    continue
                predicates = []
                if incoming:
                    predicates.append('t.' + ident(right) + ' IN ' + ids(scope[target]['ids']))
                if original_owner:
                    predicates.append('t.' + ident(left) + ' IN ' + ids(scope[model_name]['ids']))
                add('registry-many2many', rel, right, target, 't.' + ident(right), '(' + ' OR '.join(predicates) + ')',
                    target_table=target_table, owner_model=model_name,
                    owner_field=name, owner_relation_column=left, constraint_enforced=True)
                continue
            if kind == 'one2many':
                other = models.get(target)
                inverse = field['inverse_name']
                inverse_field = next((row for row in other['fields'] if row['name'] == inverse), None) if other else None
                if (not inverse_field or inverse_field['type'] != 'many2one' or inverse_field['comodel'] != model_name
                        or not any(fk['source_table'] == other['table'] and fk['source_columns'] == [inverse]
                            and fk['target_table'] == table and fk['target_columns'] == ['id'] and fk['validated']
                            for fk in catalog['foreign_keys'])):
                    blockers.append({'code': 'one2many-inverse-physical-binding-not-proven', 'model': model_name, 'field': name})
                # The real inverse FK is already captured as a physical edge.
                continue
            column = columns.get((table, name))
            if column is None:
                blockers.append({'code': 'stored-reference-column-missing', 'model': model_name, 'field': name})
                continue
            value = 't.' + ident(name)
            owner_filter = (' AND t.id IN ' + ids(scope[model_name]['ids'])) if original_owner and not incoming else ''
            if field['company_dependent'] and kind == 'many2one':
                if column['sql_type'] != 'jsonb':
                    blockers.append({'code': 'company-property-is-not-jsonb', 'model': model_name, 'field': name})
                    continue
                # Numeric ID tokens only: preserve company keys, SQL NULL and
                # JSON null. Arbitrary numbers are never treated as relations.
                owner = _owner(table, catalog)
                if owner is None:
                    blockers.append({'code': 'json-property-owner-key-not-proven', 'model': model_name, 'field': name})
                key = 'edge:' + str(len(paths))
                integer = "CASE WHEN jsonb_typeof(j.value)='number' AND (j.value#>>'{}') ~ '^[1-9][0-9]{0,9}$' THEN (j.value#>>'{}')::bigint END"
                company = "CASE WHEN j.key ~ '^[1-9][0-9]{0,9}$' THEN j.key::bigint END"
                source = "jsonb_each(CASE WHEN jsonb_typeof(" + value + ")='object' THEN " + value + " ELSE '{}'::jsonb END) j"
                predicates = []
                if incoming:
                    predicates.append(integer + ' IN ' + ids(scope[target]['ids']))
                if original_owner:
                    # A JSON-null value still has an explicit company key. It
                    # is not a target record, but its company must be bound.
                    predicates.append('(t.id IN ' + ids(scope[model_name]['ids']) + ' AND (' + integer
                        + " IS NOT NULL OR j.value='null'::jsonb))")
                predicate = '(' + ' OR '.join(predicates) + ') AND ' + company + ' BETWEEN 1 AND 2147483647 AND (' + integer + ' IS NULL OR ' + integer + '<=2147483647)'
                queries[key] = ('SELECT ' + _owner_sql(owner) + ' AS owner_pk,' + literal(target) + ' AS target_model,'
                    + integer + ' AS target_id,' + company + ' AS company_id FROM public.' + ident(table)
                    + ' t CROSS JOIN LATERAL ' + source + ' WHERE ' + predicate
                    + ' ORDER BY owner_pk,company_id,target_id')
                paths.append({'kind': 'registry-company-json', 'table': table, 'field': name, 'target_model': target,
                    'target_table': models[target]['table'], 'owner_key': owner, 'observation': key, 'owner_model': model_name})
                invalid = 'invalid-json:' + str(len(paths))
                queries[invalid] = ('SELECT ' + _owner_sql(owner) + ' AS owner_pk FROM public.' + ident(table)
                    + ' t WHERE ((' + value + " IS NOT NULL AND jsonb_typeof(" + value + ")<>'object') OR EXISTS (SELECT 1 FROM "
                    + source + ' WHERE ' + company + ' IS NULL OR ' + company + '>2147483647 OR '
                    + "(j.value<>'null'::jsonb AND (" + integer + ' IS NULL OR ' + integer + '>2147483647))))' + owner_filter + ' ORDER BY owner_pk')
                paths[-1]['invalid_observation'] = invalid
            elif kind == 'reference':
                if column['sql_type'] not in TEXT_TYPES:
                    blockers.append({'code': 'reference-column-is-not-text', 'model': model_name, 'field': name})
                    continue
                for target, selected in scope.items():
                    if not selected.get('incoming_scope', True):
                        continue
                    literals = '(' + ','.join(literal(target + ',' + str(n)) for n in selected['ids']) + ')'
                    add('registry-reference', table, name, target, "split_part(" + value + ",',',2)::bigint",
                        value + ' IN ' + literals, owner_model=model_name)
                key = 'invalid-polymorphic:' + table + '.' + name
                valid = ("CASE WHEN " + value + " ~ '^[a-z_][a-z0-9_.]+,[1-9][0-9]{0,9}$' THEN split_part("
                    + value + ",',',2)::bigint<=2147483647 AND split_part(" + value + ",',',1) IN ("
                    + ','.join(literal(model) for model in sorted(models)) + ') ELSE FALSE END')
                if original_owner:
                    outgoing = 'outbound-polymorphic:' + table + '.' + name
                    queries[outgoing] = ('SELECT ' + _owner_sql(_owner(table, catalog))
                        + " AS owner_pk,split_part(" + value + ",',',1) AS target_model,split_part(" + value
                        + ",',',2)::bigint AS target_id,NULL::integer AS company_id FROM public." + ident(table)
                        + ' t WHERE t.id IN ' + ids(scope[model_name]['ids']) + ' AND (' + valid + ') ORDER BY owner_pk,target_model,target_id')
                    paths.append({'kind': 'outbound-original-reference', 'table': table, 'field': name,
                        'owner_key': _owner(table, catalog), 'observation': outgoing, 'target_model_from_row': True})
                queries[key] = ('SELECT ' + _owner_sql(_owner(table, catalog))
                    + " AS owner_pk,encode(sha256(convert_to(" + value + "::text,'UTF8')),'hex') AS content_sha256 FROM public."
                    + ident(table) + ' t WHERE ' + value + " IS NOT NULL AND " + value + "<>'' AND NOT (" + valid + ') ORDER BY owner_pk')
                paths.append({'kind': 'malformed-or-unregistered-polymorphic-reference', 'table': table, 'field': name,
                    'owner_key': _owner(table, catalog), 'observation': key, 'semantic_binding_proven': False})
            elif kind == 'many2one_reference':
                discriminator = field['model_field']
                proof = field.get('discriminator_field')
                if (not proof or proof['name'] != discriminator or proof['type'] != 'char' or proof['store'] is not True
                        or proof['compute'] or proof['related'] or proof['company_dependent']
                        or column['sql_type'] not in INTEGER_TYPES or (table, discriminator) not in columns
                        or columns[table, discriminator]['sql_type'] not in TEXT_TYPES):
                    blockers.append({'code': 'polymorphic-discriminator-binding-not-proven', 'model': model_name, 'field': name})
                    continue
                for target, selected in scope.items():
                    if not selected.get('incoming_scope', True):
                        continue
                    add('registry-many2one-reference', table, name, target, value,
                        't.' + ident(discriminator) + '=' + literal(target) + ' AND ' + value + ' IN ' + ids(selected['ids']),
                        owner_model=model_name, discriminator_column=discriminator)
                key = 'invalid-polymorphic:' + table + '.' + name
                known_model = 't.' + ident(discriminator) + ' IN (' + ','.join(literal(model) for model in sorted(models)) + ')'
                if original_owner:
                    outgoing = 'outbound-polymorphic:' + table + '.' + name
                    queries[outgoing] = ('SELECT ' + _owner_sql(_owner(table, catalog)) + ' AS owner_pk,t.' + ident(discriminator)
                        + ' AS target_model,' + value + ' AS target_id,NULL::integer AS company_id FROM public.' + ident(table)
                        + ' t WHERE t.id IN ' + ids(scope[model_name]['ids']) + ' AND ' + value
                        + '>0 AND ' + value + '<=2147483647 AND ' + known_model + ' ORDER BY owner_pk,target_model,target_id')
                    paths.append({'kind': 'outbound-original-many2one-reference', 'table': table, 'field': name,
                        'owner_key': _owner(table, catalog), 'observation': outgoing, 'target_model_from_row': True})
                queries[key] = ('SELECT ' + _owner_sql(_owner(table, catalog))
                    + " AS owner_pk,encode(sha256(convert_to(jsonb_build_array(" + value + ',t.' + ident(discriminator)
                    + ")::text,'UTF8')),'hex') AS content_sha256 FROM public." + ident(table) + ' t WHERE '
                    + value + ' IS NOT NULL AND ' + value + '<>0 AND (' + value + '<0 OR ' + value
                    + '>2147483647 OR NOT coalesce(' + known_model + ',FALSE)) ORDER BY owner_pk')
                paths.append({'kind': 'unregistered-polymorphic-model-discriminator', 'table': table, 'field': name,
                    'owner_key': _owner(table, catalog), 'observation': key, 'semantic_binding_proven': False})
            elif kind == 'many2one':
                if column['sql_type'] not in INTEGER_TYPES:
                    blockers.append({'code': 'many2one-column-is-not-an-integer', 'model': model_name, 'field': name})
                    continue
                enforced = any(fk['source_table'] == table and fk['source_columns'] == [name]
                    and fk['target_table'] == models[target]['table'] and fk['validated'] for fk in catalog['foreign_keys'])
                predicates = []
                if incoming:
                    predicates.append(value + ' IN ' + ids(scope[target]['ids']))
                if original_owner:
                    predicates.append('(' + value + ' IS NOT NULL AND t.id IN ' + ids(scope[model_name]['ids']) + ')')
                predicate = '(' + ' OR '.join(predicates) + ')'
                add('registry-many2one', table, name, target, value, predicate,
                    target_table=models[target]['table'],
                    owner_model=model_name, constraint_enforced=enforced)
                if not enforced:
                    blockers.append({'code': 'declared-many2one-without-physical-fk', 'model': model_name, 'field': name})

    # These are explicitly UNBOUND candidates, never a model/table binding.
    # A hash/number match in arbitrary JSON/XML/Python is not authorization.
    serialized = {}
    for table, names in SERIALIZED_CONFIG.items():
        if table in tables and tables[table]['kind'] in ('r', 'p'):
            for name in names:
                if (table, name) in columns:
                    serialized[table, name] = 'serialized-configuration'
    for binding in models.values():
        if binding['abstract'] or binding['table'] not in tables or tables[binding['table']]['kind'] not in ('r', 'p'):
            continue
        for field in binding['fields']:
            key = binding['table'], field['name']
            if field['store'] and not field['company_dependent'] and field['type'] in ('json', 'properties', 'properties_definition') and key in columns:
                serialized[key] = 'untyped-json-without-reference-schema'
    for (table, name), kind in sorted(serialized.items()):
        owner, key = _owner(table, catalog), 'unclassified:' + table + '.' + name
        queries[key] = ('SELECT ' + _owner_sql(owner) + " AS owner_pk,encode(sha256(convert_to(t." + ident(name)
            + "::text,'UTF8')),'hex') AS content_sha256 FROM public." + ident(table)
            + ' t WHERE t.' + ident(name) + " IS NOT NULL AND t." + ident(name) + "::text NOT IN ('','{}','[]','null') ORDER BY owner_pk")
        paths.append({'kind': kind, 'table': table, 'field': name, 'owner_key': owner,
            'observation': key, 'semantic_binding_proven': False})
    return queries, paths, blockers


def endpoint_queries(paths, observations, registry):
    """Bind every observed endpoint and every composite owner's FK component."""
    by_table = {}
    models = registry_models(registry)
    for name, row in models.items():
        if not row['abstract']:
            by_table.setdefault(row['table'], []).append(name)
    endpoints = {}
    for path in paths:
        for row in observations[path['observation']]:
            if path.get('target_model_from_row') and row.get('target_id') is not None:
                binding = models.get(row.get('target_model'))
                require(binding and not binding['abstract'] and binding['table'], 'observed-polymorphic-target-registry-binding-not-proven')
                endpoints.setdefault((binding['table'], row['target_model']), set()).add(row['target_id'])
            elif path.get('target_table') and row.get('target_id') is not None:
                endpoints.setdefault((path['target_table'], path.get('target_model')), set()).add(row['target_id'])
            if row.get('company_id') is not None:
                company = models.get('res.company')
                require(company and not company['abstract'], 'company-endpoint-registry-binding-not-proven')
                endpoints.setdefault((company['table'], 'res.company'), set()).add(row['company_id'])
            for fk in (path.get('owner_key') or {}).get('component_foreign_keys', []):
                if fk['target_schema'] == 'public' and fk['target_columns'] == ['id'] and len(fk['source_columns']) == 1 and fk['validated']:
                    value = (row.get('owner_pk') or {}).get(fk['source_columns'][0])
                    if value is not None:
                        bound_names = by_table.get(fk['target_table'], [])
                        model = bound_names[0] if len(bound_names) == 1 else None
                        endpoints.setdefault((fk['target_table'], model), set()).add(value)
    queries, contracts = {}, []
    for (table, model), values in sorted(endpoints.items(), key=lambda row: str(row[0])):
        name = 'endpoint:' + str(len(contracts))
        queries[name] = ('SELECT id,tableoid::regclass::text AS physical_table,'
            "encode(sha256(convert_to(to_jsonb(t)::text,'UTF8')),'hex') AS row_sha256 FROM public."
            + ident(table) + ' t WHERE id IN ' + ids(values) + ' ORDER BY id,physical_table')
        contract = {'table': table, 'model': model, 'ids': sorted(values), 'observation': name}
        if model:
            alias = name + ':aliases'
            queries[alias] = ('SELECT id,module,name,model,res_id,noupdate FROM ir_model_data WHERE model='
                + literal(model) + ' AND res_id IN ' + ids(values) + ' ORDER BY id')
            contract['alias_observation'] = alias
        contracts.append(contract)
    return queries, contracts


def assess(catalog, first, second, registry, scope, aliases):
    require(first == second, 'concurrent-reference-or-occupant-change')
    queries, paths, blockers = compile_paths(catalog, registry, scope)
    require(set(queries) <= set(first), 'reference-observations-incomplete')
    for path in paths:
        rows = first[path['observation']]
        require(isinstance(rows, list), 'reference-rows-shape')
        if path.get('invalid_observation') and first[path['invalid_observation']]:
            blockers.append({'code': 'malformed-company-property', 'table': path['table'], 'field': path['field']})
        if path.get('semantic_binding_proven') is False and rows:
            blockers.append({'code': path['kind'], 'table': path['table'], 'field': path['field'], 'nonempty_rows': len(rows)})
        if (path.get('target_model') or path.get('target_model_from_row')) and any(row['owner_pk'] is None for row in rows):
            blockers.append({'code': 'nonempty-reference-owner-not-bound', 'table': path['table'], 'field': path['field']})
    existing = {row['id']: row for row in catalog['alias_occupants']}
    by_name = {(row['module'], row['name']): row for row in catalog['alias_occupants']}
    alias_plan = []
    for row in aliases:
        occupant, nominal = existing.get(row['id']), by_name.get((row['module'], row['name']))
        exact = occupant == row and nominal == row
        alias_plan.append({'original': row, 'primary_key_occupant': occupant, 'nominal_alias': nominal,
            'identity_exact': exact, 'write_authorized': False})
        if not exact:
            blockers.append({'code': 'original-xmlid-pk-or-owner-not-adopted', 'xmlid': row['module'] + '.' + row['name'], 'original_pk': row['id']})
    occupants = {}
    for model, selected in scope.items():
        rows = catalog.get('target-occupants:' + model, [])
        aliases_now = catalog.get('target-aliases:' + model, [])
        require(len({row['id'] for row in rows}) == len(rows), 'multiple-physical-occupants-for-target-id')
        occupants[model] = {'physical_table': selected['table'], 'expected_ids': selected['ids'],
            'rows': rows, 'aliases': aliases_now}
        if selected.get('original_expected', True) and set(selected['ids']) - {row['id'] for row in rows}:
            blockers.append({'code': 'referenced-target-record-missing', 'model': model,
                'ids': sorted(set(selected['ids']) - {row['id'] for row in rows})})
    action = catalog.get('action_462', [])
    if len(action) != 1 or action[0]['type'] != 'ir.actions.report':
        blockers.append({'code': 'original-report462-occupied-by-another-action-family-or-missing'})
    return {'schema': 1, 'read_only': True, 'database_writes': False, 'orm_loaded': False,
        'scope': scope, 'paths': [dict(path, rows=first[path['observation']]) for path in paths],
        'target_identities': occupants, 'action_462_physical_occupants': catalog.get('action_462', []),
        'blockers': blockers, 'alias_identity_plan': alias_plan, 'two_snapshots_exact': True,
        'physical_reference_paths': sum('target_model' in row or row.get('target_model_from_row', False) for row in paths),
        'reference_closure_ready': not blockers, 'import_authorized': False, 'id_reservation_authorized': False,
        'selected_relocation_id': None, 'query_sha256': digest(queries),
        'recheck_required_under_writer_lock': True, 'observation_sha256': digest(first)}


def summarize(report):
    """Sanitized counts: path observations may overlap; they are not masters."""
    bound = [path for path in report['paths'] if path.get('target_model') or path.get('target_model_from_row')]
    unbound = [path for path in report['paths'] if not (path.get('target_model') or path.get('target_model_from_row'))]
    counts = {}
    for row in report['blockers']:
        counts[row['code']] = counts.get(row['code'], 0) + 1
    canonical = [row for row in report['alias_identity_plan'] if row['original']['module'] == 'hr_contract'
        and row['original']['name'] in TYPE_ALIASES]
    semantic_keys = ('module', 'name', 'model', 'res_id', 'noupdate')
    return {'database': report['database'], 'read_only': True, 'database_writes': False,
        'physical_path_contracts': report['physical_reference_paths'],
        'bound_path_observation_rows': sum(len(path['rows']) for path in bound),
        'unclassified_candidate_rows': sum(len(path['rows']) for path in unbound),
        'observation_counts_may_include_overlapping_paths': True,
        'selects_per_complete_snapshot': len(report['sql_queries']), 'two_complete_snapshots_exact': report['two_snapshots_exact'],
        'endpoint_contracts': len(report['endpoint_identities']), 'blockers': len(report['blockers']),
        'blockers_by_code': dict(sorted(counts.items())),
        'canonical_type_aliases_nominal_model_id_noupdate_exact': sum(bool(row['nominal_alias'])
            and all(row['nominal_alias'][key] == row['original'][key] for key in semantic_keys) for row in canonical),
        'configuration_and_report_aliases_including_pk_exact': sum(row['identity_exact'] for row in report['alias_identity_plan']),
        'source_original_master_table_hashes_exact': sum(row['equal'] for row in report['original_master_value_hashes'].values()),
        'original_xmlids_proven_against_backup': report['original_xmlids_backup_proof']['original_xmlids'],
        'all_six_original_xmlid_fields_exact_to_backup': report['original_xmlids_backup_proof']['all_six_identity_fields_exact_to_backup'],
        'runtime_public_tables_and_sequences_exact': report['registry_runtime_proof']['public_snapshots_count'],
        'reference_closure_ready': report['reference_closure_ready'], 'import_authorized': False,
        'id_reservation_authorized': False, 'selected_relocation_id': None}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('capsule', 'registry-proof', 'runtime-proof', 'acceptance', 'output'):
        parser.add_argument('--' + name, required=True, type=Path)
    parser.add_argument('--expected-capsule-sha256', required=True)
    parser.add_argument('--backup-sha256', required=True)
    parser.add_argument('--backup-file', required=True, type=Path)
    args = parser.parse_args()
    require(args.expected_capsule_sha256 == CAPSULE_SHA256 and stat.S_IMODE(args.capsule.stat().st_mode) == 0o600
        and sha(args.capsule) == CAPSULE_SHA256,
        'private-sealed-capsule-required')
    require(re.fullmatch('[0-9a-f]{64}', args.backup_sha256), 'sealed-backup-sha-required')
    backup = args.backup_file.resolve()
    require(backup.is_relative_to(Path('/opt/steps-validation')) and backup.is_file()
        and not args.backup_file.is_symlink() and backup.name == 'source.dump', 'private-original-backup-file-required')
    before_stat = backup.stat()
    checksum = hashlib.sha256()
    with backup.open('rb') as stream:
        for body in iter(lambda: stream.read(1024 * 1024), b''):
            checksum.update(body)
    after_stat = backup.stat()
    require((before_stat.st_size, before_stat.st_mtime_ns) == (after_stat.st_size, after_stat.st_mtime_ns)
        and before_stat.st_size > 0 and checksum.hexdigest() == args.backup_sha256, 'backup-changed-or-digest-differs')
    source_receipt_path = backup.parent / 'passed.json'
    source_receipt = json.loads(source_receipt_path.read_text())
    require(source_receipt['mode'] == 'cerro-reference' and source_receipt['multifront'] is True
        and source_receipt['focused_development_pass'] is False and source_receipt['writes_to_source'] is False
        and source_receipt['counts']['enterprise'] == 140, 'full-native-backup-source-acceptance-required')
    identity_path = backup.parent / 'identity-before.json'
    identity_before = json.loads(identity_path.read_text())
    identity_backup_proof = prove_original_identity(backup, identity_before)
    capsule = json.loads(args.capsule.read_text())
    registry = json.loads(args.registry_proof.read_text())
    accepted = json.loads(args.acceptance.read_text())
    installation_path = args.acceptance.parent / 'module-installation.json'
    installation = json.loads(installation_path.read_text())
    database = registry['database']
    require(re.fullmatch(r'(?:COMMUNITY_PAYROLL_API_|MANAGEMENT_QA_CERRO_PAYROLL_API_)[A-Za-z0-9_]+', database), 'private-reference-database-required')
    require(type(accepted.get('operational_extensions', False)) is bool, 'ambiguous-acceptance-profile')
    expected_counts = {'community': 637, 'cerro-reference': 437} if accepted.get('operational_extensions') else {'community': 576, 'cerro-reference': 391}
    require(type(source_receipt.get('operational_extensions', False)) is bool
        and source_receipt['expected_test_count'] == (437 if source_receipt.get('operational_extensions') else 391),
        'exact-native-backup-source-profile-required')
    require(accepted['mode'] in expected_counts and accepted['expected_test_count'] == expected_counts[accepted['mode']]
        and accepted['database'] == database and accepted['writes_to_source'] is False
        and accepted['focused_development_pass'] is False and accepted['multifront'] is True,
        'accepted-full-private-reference-required')
    require(registry['acceptance_sha256'] == sha(args.acceptance)
        and registry['source_packet_sha256'] == accepted['source_files_sha256'], 'registry-acceptance-provenance-differs')
    runtime = verify_runtime_proof(args.runtime_proof, args.registry_proof, registry, args.acceptance, accepted)
    packet_path = args.acceptance.parent / 'source-files.json'
    require(sha(packet_path) == accepted['source_files_sha256'], 'accepted-source-packet-file-differs')
    require(installation['database'] == database and installation['read_only'] is True
        and installation['database_writes'] is False, 'accepted-installation-postflight-required')
    payload = Path(__file__).with_name('original_external_references_registry.py')
    require(registry['tool_sha256'] in {sha(payload), hashlib.sha256(payload.read_bytes().replace(b'\r\n', b'\n')).hexdigest()}, 'registry-payload-differs-from-trusted-tool')
    scope = scope_from_capsule(capsule)
    aliases, reference_aliases = original_aliases(capsule, identity_before)
    discovery = catalog_queries(scope, aliases)
    before = run_snapshot(database, discovery)
    require(before['transaction'] == [{'mode': 'on'}] and before['database'] == [{'database': database}], 'readonly-private-transaction-not-proven')
    scope = action_reference_scope(before, registry, scope)
    queries, paths, _ = compile_paths(before, registry, scope)
    complete_discovery = catalog_queries(scope, aliases)
    first = run_snapshot(database, dict(complete_discovery, **queries))
    endpoints, endpoint_contracts = endpoint_queries(paths, first, registry)
    complete = run_snapshot(database, dict(complete_discovery, **queries, **endpoints))
    require(all(complete[key] == value for key, value in first.items()), 'references-changed-during-endpoint-discovery')
    first = complete
    second = run_snapshot(database, dict(complete_discovery, **queries, **endpoints))
    require(all(first[name] == value for name, value in before.items()), 'catalog-drift-during-reference-discovery')
    require(first['modules'] == installation['metadata']['installed'] and not first['pending'], 'installed-graph-drifted-since-acceptance')
    report = assess({key: first[key] for key in complete_discovery}, first, second, registry, scope, aliases)
    report['endpoint_identities'] = []
    for endpoint in endpoint_contracts:
        rows = first[endpoint['observation']]
        if set(endpoint['ids']) != {row['id'] for row in rows}:
            report['blockers'].append({'code': 'physical-reference-endpoint-is-missing', 'table': endpoint['table']})
        if endpoint['model'] is None:
            report['blockers'].append({'code': 'endpoint-model-binding-ambiguous', 'table': endpoint['table']})
        report['endpoint_identities'].append(dict(endpoint, rows=rows,
            aliases=first.get(endpoint.get('alias_observation'), [])))
    report['reference_closure_ready'] = not report['blockers']
    report['original_master_value_hashes'] = {}
    for table in gate.TABLES:
        current = first['original-master-hash:' + table][0]['rows_sha256']
        expected = capsule['tables'][table]['rows_sha256']
        report['original_master_value_hashes'][table] = {'capsule_rows_sha256': expected,
            'actual_rows_sha256': current, 'equal': current == expected}
        if accepted['mode'] == 'cerro-reference' and current != expected:
            report['blockers'].append({'code': 'native-original-configuration-drift-from-pinned-capsule', 'table': table})
    report['reference_closure_ready'] = not report['blockers']
    report.update(database=database, capsule_sha256=args.expected_capsule_sha256,
        backup_sha256=args.backup_sha256, acceptance_sha256=sha(args.acceptance),
        registry_proof_sha256=sha(args.registry_proof), source_packet_sha256=accepted['source_files_sha256'],
        installation_postflight_sha256=sha(installation_path),
        tool_sha256=sha(__file__), catalog_sha256=digest(before), source_master_count=120, source_rule_count=71)
    report.update(backup_bytes=before_stat.st_size, backup_bytes_hashed=True, backup_path=str(backup),
        source_acceptance_sha256=sha(source_receipt_path), source_database=source_receipt['database'],
        identity_before_sha256=sha(identity_path), original_configuration_aliases=88,
        additional_original_report_aliases=1, reference_only_aliases=reference_aliases,
        original_xmlids_backup_proof=identity_backup_proof,
        business_reference_ids_read=True, payroll_amounts_exported=False, rules_evaluated=False,
        sql_queries=dict(complete_discovery, **queries, **endpoints), observations=first,
        path_query_sha256=report['query_sha256'], registry_payload_sha256=registry['tool_sha256'])
    report['dump_metadata_tool_sha256'] = sha(Path(__file__).with_name('original_external_references_dump.py'))
    report['registry_runtime_proof'] = runtime
    report['copy_decoder_tool_sha256'] = sha(Path(__file__).with_name('audit_stock_package_representation.py'))
    report['capsule_gate_tool_sha256'] = sha(gate.__file__)
    report['query_sha256'] = digest(report['sql_queries'])
    report['summary'] = summarize(report)
    current_stat = backup.stat()
    require((before_stat.st_dev, before_stat.st_ino, before_stat.st_size, before_stat.st_mtime_ns)
        == (current_stat.st_dev, current_stat.st_ino, current_stat.st_size, current_stat.st_mtime_ns), 'backup-changed-during-reference-audit')
    output = args.output.resolve()
    require(output.is_relative_to(Path('/opt/steps-validation')) and not output.exists() and output.parent.is_dir(), 'new-private-output-required')
    with os.fdopen(os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w') as stream:
        json.dump(report, stream, indent=2)
    print(json.dumps({'output': str(output), 'sha256': sha(output), 'physical_paths': report['physical_reference_paths'],
        'blockers': len(report['blockers']), 'reference_closure_ready': report['reference_closure_ready'],
        'import_authorized': False, 'database_writes': False}))


if __name__ == '__main__':
    main()
