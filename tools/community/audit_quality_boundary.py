"""Read-only native quality identity/API/storage boundary on the private H copy.

No source bodies, record payloads, ORM, production connection, DDL or DML.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess


DATABASE = 'MANAGEMENT_QA_CERRO_PAYROLL_API_MULTIFRONT_20261030H'


def statements():
    return {
        'transaction': 'SELECT current_database() AS database,current_setting(\'transaction_read_only\') AS read_only',
        'modules': "SELECT name,latest_version,license,state FROM ir_module_module WHERE name IN ('quality','quality_control','step_qa','step_export_traceability','step_agriculture_records','quality_control_oca') ORDER BY name",
        'models': "SELECT id,model,state FROM ir_model WHERE model LIKE 'quality.%' OR model IN ('step.agriculture.inspection','step.agriculture.inspection.line','step.agriculture.advisory') ORDER BY model",
        'fields': "SELECT id,model,name,ttype,relation,relation_field,required,readonly,store,related,on_delete FROM ir_model_fields WHERE model LIKE 'quality.%' OR relation LIKE 'quality.%' OR model IN ('step.agriculture.inspection','step.agriculture.inspection.line','step.agriculture.advisory') ORDER BY model,name",
        'acl': "SELECT a.id,m.model,a.group_id,a.active,a.perm_read,a.perm_write,a.perm_create,a.perm_unlink FROM ir_model_access a JOIN ir_model m ON m.id=a.model_id WHERE m.model LIKE 'quality.%' ORDER BY m.model,a.id",
        'rules': "SELECT r.id,m.model,r.domain_force,r.active,r.global,r.perm_read,r.perm_write,r.perm_create,r.perm_unlink FROM ir_rule r JOIN ir_model m ON m.id=r.model_id WHERE m.model LIKE 'quality.%' ORDER BY m.model,r.id",
        'field_groups': "SELECT f.model,f.name,r.group_id FROM ir_model_fields_group_rel r JOIN ir_model_fields f ON f.id=r.field_id WHERE f.model LIKE 'quality.%' ORDER BY f.model,f.name,r.group_id",
        'groups': "SELECT id,module,name,res_id,noupdate FROM ir_model_data WHERE model='res.groups' AND (module LIKE 'quality%' OR module='step_qa') ORDER BY module,name",
        'xmlids': "SELECT id,module,name,model,res_id,noupdate FROM ir_model_data WHERE module IN ('step_qa','step_export_traceability') OR model LIKE 'quality.%' ORDER BY module,name",
        'tables': "SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND c.relkind IN ('r','p') AND c.relname LIKE 'quality_%' ORDER BY c.relname",
        'columns': "SELECT table_name,column_name,data_type,is_nullable FROM information_schema.columns WHERE table_schema='public' AND table_name LIKE 'quality_%' ORDER BY table_name,ordinal_position",
        'constraints': "SELECT c.conname,r.relname,c.contype,c.convalidated,pg_get_constraintdef(c.oid) AS definition FROM pg_constraint c JOIN pg_class r ON r.oid=c.conrelid WHERE r.relname LIKE 'quality_%' ORDER BY r.relname,c.conname",
        'views': "SELECT id,model,type,inherit_id,active,encode(sha256(convert_to(arch_db::text,'UTF8')),'hex') AS architecture_sha256 FROM ir_ui_view WHERE model LIKE 'quality.%' ORDER BY model,id",
        'sequences': "SELECT id,code,company_id,number_next,implementation,active FROM ir_sequence WHERE code LIKE 'quality.%' OR code LIKE 'qc.%' ORDER BY id",
    }


def payload(database, queries):
    if database != DATABASE:
        raise ValueError('Only the authorized private H copy is admitted')
    result = ['BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY;']
    for name, query in queries.items():
        if not re.fullmatch('[a-z_][a-z_0-9:]*', name) or not query.lstrip().upper().startswith('SELECT ') or ';' in query:
            raise ValueError('Only reviewed SELECT metadata queries are admitted')
        result.append("SELECT jsonb_build_object('section','" + name + "','rows',coalesce(jsonb_agg(t),'[]'::jsonb)) FROM (" + query + ') t;')
    return '\n'.join(result + ['ROLLBACK;'])


def snapshot(database, queries):
    value = subprocess.check_output(['sudo', '-u', 'postgres', 'env', 'PGOPTIONS=-c default_transaction_read_only=on',
        'psql', '-XAtq', '-v', 'ON_ERROR_STOP=1', '-d', database], input=payload(database, queries), text=True)
    entries = [json.loads(line) for line in value.splitlines() if line]
    result = {entry['section']: entry['rows'] for entry in entries}
    if len(result) != len(entries) or set(result) != set(queries) or result['transaction'] != [{'database': database, 'read_only': 'on'}]:
        raise ValueError('Incomplete or non-readonly quality boundary snapshot')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', default=DATABASE)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if not output.parent.is_dir() or not output.is_relative_to(Path('/opt/steps-validation')) or output.exists():
        raise ValueError('A new private evidence destination is required')
    before = snapshot(args.database, statements())
    queries = statements()
    for row in before['tables']:
        name = row['relname']
        if not re.fullmatch('quality_[a-z_0-9]+', name):
            raise ValueError('Unreviewed native quality table')
        queries['table:' + name] = 'SELECT count(*) AS rows,md5(coalesce(string_agg(to_jsonb(t)::text,E\'\\n\' ORDER BY to_jsonb(t)::text),\'\')) AS stored_rows_md5 FROM "' + name + '" t'
    current = snapshot(args.database, queries)
    after = snapshot(args.database, queries)
    if current != after or any(current[name] != value for name, value in before.items()):
        raise ValueError('Native quality data or metadata changed during the audit')
    report = {'schema': 1, 'database': args.database, 'read_only': True, 'orm_loaded': False,
        'database_writes': False, 'source_bodies_read': False, 'row_payloads_exported': False,
        'native_identity_converted': False, 'original_consumers_community_certified': False,
        'before': current, 'after': after, 'tool_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    with os.fdopen(os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w') as stream:
        json.dump(report, stream, indent=2)
    print('QUALITY_NATIVE_BOUNDARY_AUDITED', len(before['models']), 'models;', len(before['tables']), 'tables; no conversion')


if __name__ == '__main__':
    main()
