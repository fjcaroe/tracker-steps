"""Catalog-only input storage evidence; no salary rows, ORM or conversion.

Binary64 examples are synthetic mathematical warnings, never customer payroll
calculations or a policy authorizing an ALTER or historical materialization.
"""
import argparse
import ast
from decimal import Decimal
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess


DATABASES = {'COMMUNITY_PAYROLL_API_INPUTS_20261029C',
             'MANAGEMENT_QA_CERRO_PAYROLL_API_INPUTS_20261029C', 'SyS'}
OCA_PIN = '4c71cd42e46a09a7512d92f5c63c0a9f7c26ad3e'
OFFICIAL_PIN = '4b4efe68291d6def5bb7d2e1f2b829e0cda577d4'
FIELDS = ('amount', 'code', 'contract_id', 'input_type_id', 'payslip_id')
MODEL = 'hr.payslip.input'


def digest(value):
    return hashlib.sha256(value).hexdigest()


def metadata_queries():
    fields = "SELECT id FROM ir_model_fields WHERE model='hr.payslip.input' AND name IN ('amount','code','contract_id','input_type_id','payslip_id')"
    return {
        'transaction': "SELECT current_database() AS database,current_setting('transaction_read_only') AS read_only",
        'postgres': "SELECT current_setting('server_version') AS server_version,current_setting('server_version_num') AS server_version_num",
        'model': "SELECT id,model,state FROM ir_model WHERE model='hr.payslip.input'",
        'fields': "SELECT id,model,name,ttype,relation,relation_field,required,readonly,store,related,company_dependent,translate,on_delete FROM ir_model_fields WHERE id IN (" + fields + ') ORDER BY name',
        'field_groups': 'SELECT field_id,group_id FROM ir_model_fields_group_rel WHERE field_id IN (' + fields + ') ORDER BY field_id,group_id',
        'xmlids': "SELECT id,module,name,model,res_id,noupdate FROM ir_model_data WHERE (model='ir.model' AND res_id IN (SELECT id FROM ir_model WHERE model='hr.payslip.input')) OR (model='ir.model.fields' AND res_id IN (" + fields + ')) ORDER BY model,module,name',
        'table': "SELECT c.oid,n.nspname,c.relname,c.relkind FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND c.relname='hr_payslip_input'",
        'columns': "SELECT a.attnum,a.attname,t.typname,a.atttypmod,format_type(a.atttypid,a.atttypmod) AS formatted_type,a.attnotnull,a.atthasdef,pg_get_expr(d.adbin,d.adrelid) AS default_expression,i.numeric_precision,i.numeric_precision_radix,i.numeric_scale FROM pg_attribute a JOIN pg_type t ON t.oid=a.atttypid LEFT JOIN pg_attrdef d ON d.adrelid=a.attrelid AND d.adnum=a.attnum LEFT JOIN information_schema.columns i ON i.table_schema='public' AND i.table_name='hr_payslip_input' AND i.column_name=a.attname WHERE a.attrelid=to_regclass('public.hr_payslip_input') AND a.attnum>0 AND NOT a.attisdropped AND a.attname IN ('id','amount','code','contract_id','input_type_id','payslip_id') ORDER BY a.attnum",
        'constraints': "SELECT k.oid,k.conname,k.contype,k.convalidated,k.condeferrable,k.condeferred,k.confdeltype,k.confupdtype,k.conkey,k.confkey,CASE WHEN k.confrelid!=0 THEN k.confrelid::regclass::text END AS referenced_table,pg_get_constraintdef(k.oid) AS definition FROM pg_constraint k WHERE k.conrelid=to_regclass('public.hr_payslip_input') ORDER BY k.conname",
        'indexes': "SELECT i.indexrelid::regclass::text AS name,i.indisprimary,i.indisunique,i.indisvalid,pg_get_indexdef(i.indexrelid) AS definition FROM pg_index i WHERE i.indrelid=to_regclass('public.hr_payslip_input') ORDER BY i.indexrelid::regclass::text",
    }


def sql_payload(queries):
    statements = ['BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY;']
    for section, query in queries.items():
        assert query.startswith('SELECT ') and ';' not in query
        assert section.replace('_', '').isalnum()
        statements.append("SELECT jsonb_build_object('section','" + section
            + "','rows',coalesce(jsonb_agg(t),'[]'::jsonb)) FROM (" + query + ') t;')
    return '\n'.join(statements + ['ROLLBACK;'])


def snapshot(database):
    assert database in DATABASES, 'Unapproved catalog reference'
    queries = metadata_queries()
    result = subprocess.run(['sudo', '-u', 'postgres', 'env', 'PGOPTIONS=-c default_transaction_read_only=on',
        'psql', '-XAtq', '-v', 'ON_ERROR_STOP=1', '-d', database], input=sql_payload(queries),
        text=True, capture_output=True, check=True)
    rows = [json.loads(line) for line in result.stdout.splitlines() if line]
    data = {row['section']: row['rows'] for row in rows}
    assert len(data) == len(rows) == len(queries), 'Incomplete or duplicate catalog sections'
    assert data['transaction'] == [{'database': database, 'read_only': 'on'}]
    assert len(data['table']) == len(data['model']) == 1
    assert {row['name'] for row in data['fields']} == set(FIELDS)
    assert 'amount' in {row['attname'] for row in data['columns']}
    return data


def source_provenance(official, oca):
    result = {}
    for name, root, pin, remote, files in (
            ('official', official, OFFICIAL_PIN, 'https://github.com/odoo/odoo.git', ('odoo/fields.py', 'odoo/models.py')),
            ('oca', oca, OCA_PIN, 'https://github.com/OCA/payroll.git', ('payroll/models/hr_payslip_input.py', 'payroll/models/hr_payslip.py', 'payroll/__manifest__.py'))):
        command = lambda *args: subprocess.check_output(['git', '-C', str(root), *args], text=True).strip()
        assert command('rev-parse', 'HEAD') == pin
        assert command('remote', 'get-url', 'origin') == remote
        assert not command('status', '--porcelain')
        result[name] = {'revision': pin, 'files': {item: digest((root / item).read_bytes()) for item in files}}
    assert ast.literal_eval((oca / 'payroll/__manifest__.py').read_text(encoding='utf-8-sig'))['license'] == 'LGPL-3'
    result['source_bodies_exported'] = False
    result['reference_sources_only'] = True
    result['effective_database_source_provenance_certified'] = False
    return result


def identity_projection(data):
    """Only explicitly present safe metadata attributes, including partial registries."""
    fields = {}
    def walk(value):
        if isinstance(value, dict):
            if value.get('model') == MODEL and value.get('name') in FIELDS and type(value.get('id')) is int:
                row = {key: value[key] for key in ('id', 'model', 'name', 'store', 'related') if key in value}
                if 'related' in row and row['related'] in (False, ''):
                    row['related'] = None
                previous = fields.setdefault(row['name'], {})
                for key, item in row.items():
                    assert key not in previous or previous[key] == item, 'Conflicting identity metadata'
                    previous[key] = item
            for item in value.values():
                walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)
    walk(data)
    return fields


def identity_provenance(path, metadata):
    if path is None:
        return {'provided': False, 'complete': False, 'basis': 'two-current-catalog-captures'}
    body = path.read_bytes()
    prior = identity_projection(json.loads(body))
    current = {row['name']: row for row in metadata['fields']}
    for name, values in prior.items():
        assert all(current[name][key] == value for key, value in values.items()), 'Identity snapshot differs from current catalog'
    return {'provided': True, 'sha256': digest(body), 'fields': prior,
            'complete': set(prior) == set(FIELDS), 'missing_fields': sorted(set(FIELDS) - set(prior)),
            'compared_attributes': ['id', 'model', 'name', 'store', 'related'],
            'present_metadata_equal': True, 'basis': 'prior-identity-and-two-current-captures'}


def classify(source, target):
    source_columns = {row['attname']: row for row in source['columns']}
    target_columns = {row['attname']: row for row in target['columns']}
    source_fields = {row['name']: row for row in source['fields']}
    target_fields = {row['name']: row for row in target['fields']}
    result = {}
    for name in ('amount', 'code', 'contract_id'):
        first, last = source_columns.get(name), target_columns.get(name)
        decimal_binary = bool(first and last and first['typname'] == 'numeric' and last['typname'] == 'float8')
        storage = lambda column: None if column is None else {key: value for key, value in column.items() if key != 'attnum'}
        result[name] = {'source_column': first, 'target_column': last,
            'physical_contract_equal': storage(first) == storage(last),
            'source_field': source_fields[name], 'target_field': target_fields[name],
            'related_to_stored': bool(source_fields[name]['related'] and not source_fields[name]['store'] and target_fields[name]['store']),
            'decimal_to_binary64_difference': decimal_binary,
            'potential_precision_loss_if_converted': decimal_binary,
            'row_loss_observed': False, 'customer_value_projection_performed': False}
    return {'fields': result, 'conversion_authorized': False, 'ddl_or_dml_plan': None,
        'precision_preservation_certified': False, 'historical_materialization_certified': False,
        'identity_adopted': False, 'row_data_assessed': False,
        'required_before_any_alteration': ['explicit decimal precision policy', 'lossless original storage and identity plan',
            'authoritative related-field materialization policy', 'restorable private conversion and complete preservation proof']}


def synthetic_decimal_binary64_projection(value):
    """Permissive classification of supplied synthetic examples, never DB values."""
    if value is None:
        return {'sql_null_preserved': True, 'numerically_exact': True, 'synthetic_only': True}
    if isinstance(value, bool):
        raise ValueError('A Boolean is not a decimal amount example')
    original = Decimal(value)
    if not original.is_finite():
        return {'numerically_exact': False, 'reason': 'nonfinite', 'synthetic_only': True}
    projected = float(original)
    if not math.isfinite(projected):
        return {'numerically_exact': False, 'reason': 'overflow', 'synthetic_only': True}
    exact = Decimal.from_float(projected) == original
    return {'numerically_exact': exact, 'reason': 'exact' if exact else ('underflow' if projected == 0 else 'precision'),
        'negative_zero_preserved': not original.is_zero() or Decimal.from_float(projected).is_signed() == original.is_signed(),
        'synthetic_only': True}


def write_private(path, value):
    assert path.parent.is_dir() and Path('/opt/steps-validation') in path.resolve().parents
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w') as stream:
        json.dump(value, stream, indent=2)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    capture = commands.add_parser('capture')
    capture.add_argument('--database', choices=sorted(DATABASES), required=True)
    capture.add_argument('--identity-file', type=Path)
    capture.add_argument('--official', type=Path, required=True)
    capture.add_argument('--oca', type=Path, required=True)
    compare = commands.add_parser('compare')
    for name in ('community', 'native', 'sys'):
        compare.add_argument('--' + name, type=Path, required=True)
    for command in (capture, compare):
        command.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    tool_sha = digest(Path(__file__).read_bytes())
    if args.command == 'capture':
        source = source_provenance(args.official, args.oca)
        before = snapshot(args.database)
        after = snapshot(args.database)
        assert before == after, 'Catalog changed during the audit'
        report = {'schema': 1, 'database': args.database, 'read_only': True, 'orm_loaded': False,
            'salary_rows_read': False, 'salary_amounts_read': False, 'database_writes': False,
            'rules_evaluated': False, 'conversion_authorized': False, 'source_bodies_exported': False,
            'metadata_before': before, 'metadata_after': after, 'metadata_captures_equal': True,
            'source_provenance': source, 'identity_provenance': identity_provenance(args.identity_file, before),
            'tool_sha256': tool_sha}
    else:
        reports, hashes = {}, {}
        expected = {'community': 'COMMUNITY_PAYROLL_API_INPUTS_20261029C',
                    'native': 'MANAGEMENT_QA_CERRO_PAYROLL_API_INPUTS_20261029C', 'sys': 'SyS'}
        for label, database in expected.items():
            body = getattr(args, label).read_bytes()
            report = json.loads(body)
            assert report['database'] == database and report['tool_sha256'] == tool_sha
            assert report['metadata_before'] == report['metadata_after'] and report['read_only']
            assert not any(report[key] for key in ('orm_loaded', 'salary_rows_read', 'salary_amounts_read', 'database_writes', 'conversion_authorized'))
            reports[label], hashes[label] = report, digest(body)
        report = {'schema': 1, 'tool_sha256': tool_sha, 'reports_sha256': hashes, 'catalog_only': True,
            'native_to_community': classify(reports['native']['metadata_before'], reports['community']['metadata_before']),
            'sys_to_community': classify(reports['sys']['metadata_before'], reports['community']['metadata_before']),
            'conversion_authorized': False, 'rows_read': False, 'customer_precision_assessed': False}
    write_private(args.output, report)
    print(json.dumps({'command': args.command, 'evidence_sha256': digest(args.output.read_bytes()),
                      'read_only': True, 'conversion_authorized': False}))


if __name__ == '__main__':
    main()
