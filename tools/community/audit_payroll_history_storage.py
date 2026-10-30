"""Four catalog contracts and passive registry metadata, never salary rows.

CLI snapshots use PostgreSQL READ ONLY after sudo and a clean environment.
inspect_registry() only accepts an already loaded private readonly registry;
it neither starts Odoo nor evaluates a field, record, default or compute.
Normal installations and anchored original identities are separate profiles.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess


PRIVATE = re.compile(r'(?:COMMUNITY_PAYROLL_API_[A-Za-z0-9_]+|MANAGEMENT_QA_CERRO_PAYROLL_API_[A-Za-z0-9_]+)')
PROFILES = ('normal-community', 'anchored-community', 'native-reference')
SPECS = (
    ('hr.payslip.line', 'hr_payslip_line', 'name', 'varchar', True, False),
    ('hr.salary.rule', 'hr_salary_rule', 'name', 'jsonb', True, True),
    ('hr.payslip.worked_days', 'hr_payslip_worked_days', 'name', 'varchar', False, False),
    ('hr.contract', 'hr_contract', 'resource_calendar_id', 'int4', False, False),
)


def need(value, code):
    if not value:
        raise ValueError('history-storage-' + code)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def queries():
    predicates = ' OR '.join("(model='%s' AND name='%s')" % (model, name) for model, _, name, *_ in SPECS)
    physical = ' OR '.join("(c.relname='%s' AND a.attname='%s')" % (table, name) for _, table, name, *_ in SPECS)
    return {
        'transaction': "SELECT current_database() AS database,current_setting('transaction_read_only') AS read_only,current_setting('default_transaction_read_only') AS default_read_only,current_setting('transaction_isolation') AS isolation",
        'providers': "SELECT name,latest_version,license FROM ir_module_module WHERE state='installed' ORDER BY name",
        'models': "SELECT id,model,state FROM ir_model WHERE model IN ('hr.payslip.line','hr.salary.rule','hr.payslip.worked_days','hr.contract') ORDER BY model",
        'fields': "SELECT id,model,name,ttype,required,store,translate,relation,on_delete FROM ir_model_fields WHERE " + predicates + ' ORDER BY model,name',
        'field_xmlids': "SELECT id,module,name,model,res_id,noupdate FROM ir_model_data WHERE model='ir.model.fields' AND res_id IN (SELECT id FROM ir_model_fields WHERE " + predicates + ') ORDER BY module,name',
        'columns': "SELECT c.relname AS table_name,a.attname AS column_name,t.typname,a.atttypmod AS typmod,a.attnotnull AS not_null,a.atthasdef AS has_default FROM pg_attribute a JOIN pg_class c ON c.oid=a.attrelid JOIN pg_namespace n ON n.oid=c.relnamespace JOIN pg_type t ON t.oid=a.atttypid WHERE n.nspname='public' AND NOT a.attisdropped AND a.attnum>0 AND (" + physical + ') ORDER BY c.relname,a.attname',
        'calendar_fk': "SELECT k.conname,k.confdeltype,k.confupdtype,k.convalidated,k.condeferrable,k.condeferred,c.relname AS referenced_table,b.attname AS referenced_column FROM pg_constraint k JOIN pg_attribute a ON a.attrelid=k.conrelid AND k.conkey=ARRAY[a.attnum]::smallint[] JOIN pg_attribute b ON b.attrelid=k.confrelid AND k.confkey=ARRAY[b.attnum]::smallint[] JOIN pg_class c ON c.oid=k.confrelid JOIN pg_namespace n ON n.oid=c.relnamespace WHERE k.contype='f' AND k.conrelid='public.hr_contract'::regclass AND a.attname='resource_calendar_id' AND n.nspname='public' ORDER BY k.conname",
    }


def payload():
    statements = ['BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY;']
    for name, statement in queries().items():
        need(statement.startswith('SELECT ') and ';' not in statement, 'static-select-required')
        statements.append("SELECT jsonb_build_object('section','" + name + "','rows',coalesce(jsonb_agg(x),'[]'::jsonb)) FROM (" + statement + ') x;')
    return '\n'.join(statements + ['ROLLBACK;'])


def command(database):
    need(isinstance(database, str) and PRIVATE.fullmatch(database), 'private-database-required')
    return ['/usr/bin/sudo', '-n', '-u', 'postgres', '/usr/bin/env', '-i',
        'PATH=/usr/bin:/bin', 'HOME=/nonexistent', 'PGHOST=/var/run/postgresql',
        'PGPASSFILE=/dev/null', 'PGSERVICEFILE=/dev/null',
        'PGOPTIONS=-c default_transaction_read_only=on', '/usr/bin/psql', '-X', '--no-password',
        '-qAt', '-v', 'ON_ERROR_STOP=1', '--host=/var/run/postgresql', '--username=postgres', '--dbname=' + database]


def snapshot(database):
    invoked = subprocess.run(command(database), input=payload(), text=True, capture_output=True)
    need(invoked.returncode == 0, 'readonly-catalog-query-rejected')
    rows = [json.loads(line) for line in invoked.stdout.splitlines() if line]
    result = {row['section']: row['rows'] for row in rows}
    need(len(rows) == len(result) == len(queries()) and set(result) == set(queries()), 'complete-unique-catalog-required')
    need(result['transaction'] == [{'database': database, 'read_only': 'on', 'default_read_only': 'on',
        'isolation': 'repeatable read'}], 'actual-postgresql-readonly-required')
    return result


def inspect_registry(env):
    """Metadata only, called by the coordinator inside its readonly bootstrap."""
    need(isinstance(env.cr.dbname, str) and PRIVATE.fullmatch(env.cr.dbname), 'private-registry-required')
    need(env.registry.ready is True and env.registry.db_name == env.cr.dbname, 'loaded-same-registry-required')
    need(env.cr.readonly is True, 'odoo-readonly-cursor-required')
    env.cr.execute('SHOW transaction_read_only')
    need(env.cr.fetchone() == ('on',), 'actual-registry-transaction-readonly-required')
    result = []
    for model, table, name, *_ in SPECS:
        cls = env.registry[model]
        need(cls._table == table and cls._auto and not cls._transient, 'original-stored-model-required')
        field = cls._fields[name]
        need(field.model_name == model and field.name == name, 'actual-field-binding-required')
        result.append({'model': model, 'table': table, 'name': name, 'type': field.type,
            'required': bool(field.required), 'translate': bool(field.translate), 'store': bool(field.store),
            'column_type': list(field.column_type) if field.column_type else None,
            'related': list(field.related) if isinstance(field.related, (tuple, list)) else field.related or None,
            'compute_declared': bool(field.compute), 'groups': field.groups or None,
            'comodel_name': getattr(field, 'comodel_name', None), 'ondelete': getattr(field, 'ondelete', None)})
    return {'schema': 1, 'database': env.cr.dbname, 'read_only': True, 'registry_loaded_by_caller': True,
        'fields': result, 'records_read': False, 'computes_evaluated': False, 'database_writes': False}


def assess(catalog, runtime=None):
    fields = {(row['model'], row['name']): row for row in catalog['fields']}
    columns = {(row['table_name'], row['column_name']): row for row in catalog['columns']}
    need(len(fields) == len(columns) == len(SPECS) == len(catalog['fields']) == len(catalog['columns']),
        'exact-four-fields-and-columns-required')
    result = {}
    for model, table, name, sql_type, required, translate in SPECS:
        field, column = fields[(model, name)], columns[(table, name)]
        expected_type = 'many2one' if name == 'resource_calendar_id' else 'char'
        good = (field['ttype'] == expected_type and field['required'] is required
            and field['store'] is True and field['translate'] is translate and column['typname'] == sql_type
            and column['typmod'] == -1 and column['not_null'] is required and column['has_default'] is False)
        result[model + '.' + name] = {'physical_and_field_metadata_match': good,
            'column': column, 'field_id': field['id']}
    foreign = catalog['calendar_fk']
    fk_ok = len(foreign) == 1 and all(foreign[0].get(key) == value for key, value in {
        'confdeltype': 'n', 'confupdtype': 'a', 'convalidated': True, 'condeferrable': False,
        'condeferred': False, 'referenced_table': 'resource_calendar', 'referenced_column': 'id'}.items())
    runtime_ok = None
    if runtime is not None:
        need(runtime.get('read_only') is True and runtime.get('records_read') is False
            and runtime.get('computes_evaluated') is False and runtime.get('database_writes') is False,
            'passive-registry-witness-required')
        need(runtime.get('database') == catalog['transaction'][0]['database'], 'registry-catalog-database-mismatch')
        actual = {(row['model'], row['name']): row for row in runtime['fields']}
        need(len(actual) == len(runtime['fields']) == len(SPECS), 'exact-runtime-fields-required')
        runtime_ok = all(actual[(model, name)]['required'] is required
            and actual[(model, name)]['translate'] is translate and actual[(model, name)]['store'] is True
            and actual[(model, name)]['type'] == ('many2one' if name == 'resource_calendar_id' else 'char')
            and actual[(model, name)]['column_type'] == [kind, kind]
            and actual[(model, name)]['table'] == table for model, table, name, kind, required, translate in SPECS)
        calendar = actual[('hr.contract', 'resource_calendar_id')]
        runtime_ok = runtime_ok and calendar['ondelete'] == 'set null' and calendar['comodel_name'] == 'resource.calendar'
    return {'contracts': result, 'calendar_fk_set_null': fk_ok, 'runtime_metadata_match': runtime_ok,
        'catalog_contracts_closed': sum(row['physical_and_field_metadata_match'] for row in result.values()),
        'all_four_catalog_contracts_match': all(row['physical_and_field_metadata_match'] for row in result.values()) and fk_ok,
        'other_columns_waived': [], 'historical_rows_assessed': False, 'adoption_authorized': False,
        'financial_certified': False, 'integral_conversion': False}


def compare(source, target):
    need(source['profile'] == 'native-reference' and target['profile'] in PROFILES[:2], 'explicit-source-target-profiles-required')
    for value in (source, target):
        need(value['metadata_before'] == value['metadata_after'] and value['read_only'] is True
            and value['database_writes'] is False, 'stable-readonly-captures-required')
    first, last = source['metadata_before'], target['metadata_before']
    projected = lambda data: [{key: row[key] for key in ('table_name', 'column_name', 'typname', 'typmod', 'not_null', 'has_default')}
        for row in data['columns']]
    identity = None
    if target['profile'] == 'anchored-community':
        identity = {name: first[name] == last[name] for name in ('models', 'fields', 'field_xmlids')}
    return {'schema': 1, 'source_database': source['database'], 'target_database': target['database'],
        'target_profile': target['profile'], 'four_column_contracts_equal': projected(first) == projected(last),
        'calendar_fk_equal': first['calendar_fk'] == last['calendar_fk'],
        'anchored_original_metadata_identity': identity,
        'normal_installation_identity_equivalence_claimed': False, 'other_columns_waived': [],
        'historical_rows_assessed': False, 'adoption_authorized': False, 'integral_conversion': False}


def write_private(path, value):
    path = Path(path)
    need(path.is_absolute() and path.parent.is_dir() and not path.exists(), 'new-private-output-required')
    raw = (json.dumps(value, indent=2, sort_keys=True) + '\n').encode()
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'wb') as stream:
        stream.write(raw)
    return digest(raw)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    capture = sub.add_parser('capture')
    capture.add_argument('--database', required=True)
    capture.add_argument('--profile', choices=PROFILES, required=True)
    capture.add_argument('--output', type=Path, required=True)
    comparison = sub.add_parser('compare')
    comparison.add_argument('--source', type=Path, required=True)
    comparison.add_argument('--target', type=Path, required=True)
    comparison.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.command == 'capture':
        before, after = snapshot(args.database), snapshot(args.database)
        need(before == after, 'catalog-changed-between-captures')
        providers = {row['name']: row for row in before['providers']}
        if args.profile == 'native-reference':
            need('hr_payroll' in providers and 'payroll' not in providers, 'actual-native-provider-required')
        else:
            need('payroll' in providers and 'step_payroll_oca_api' in providers
                and not any(row['license'] == 'OEEL-1' or row['name'] == 'hr_payroll' for row in providers.values()),
                'actual-zero-enterprise-oca-required')
        value = {'schema': 1, 'profile': args.profile, 'database': args.database,
            'tool_sha256': digest(Path(__file__).read_bytes()), 'read_only': True, 'database_writes': False,
            'metadata_before': before, 'metadata_after': after, 'assessment': assess(before),
            'orm_loaded': False, 'salary_rows_read': False, 'source_model_bodies_read': False}
    else:
        source_raw, target_raw = args.source.read_bytes(), args.target.read_bytes()
        value = compare(json.loads(source_raw), json.loads(target_raw))
        value.update(source_sha256=digest(source_raw), target_sha256=digest(target_raw), tool_sha256=digest(Path(__file__).read_bytes()))
    print(json.dumps({'evidence_sha256': write_private(args.output, value), 'database_writes': False}))


if __name__ == '__main__':
    main()
