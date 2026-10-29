"""SQL-only salary-benefit identity/storage audit; no source bodies or amounts.

Production reads are explicitly restricted to the two registered payroll
references. Nothing loads Odoo, evaluates a rule or infers a replacement model.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess


DATABASES = {'CERRO_EL_PLOMO', 'SyS'}
PREFIX = 'hr.contract.salary.'
TABLE_PREFIX = 'hr_contract_salary_'


def identifier(value):
    assert re.fullmatch('[a-z_][a-z0-9_]*', value), 'Unsafe technical SQL identifier'
    return '"' + value + '"'


def literal(value):
    return "'" + value.replace("'", "''") + "'"


def sql_payload(statements):
    parts = ['BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY;']
    for name, query in statements.items():
        assert query.lstrip().upper().startswith('SELECT '), 'SELECT-only metadata query required'
        parts.append("SELECT jsonb_build_object('section'," + literal(name)
            + ",'rows',coalesce(jsonb_agg(t),'[]'::jsonb)) FROM (" + query + ') t;')
    parts.append('ROLLBACK;')
    return '\n'.join(parts)


def snapshot(database, statements):
    assert database in DATABASES, 'Unregistered payroll reference refused'
    result = subprocess.run(['sudo', '-u', 'postgres', 'env', 'PGOPTIONS=-c default_transaction_read_only=on',
        'psql', '-XAtq', '-v', 'ON_ERROR_STOP=1', '-d', database], input=sql_payload(statements),
        text=True, capture_output=True, check=True)
    sections = [json.loads(line) for line in result.stdout.splitlines() if line]
    data = {row['section']: row['rows'] for row in sections}
    assert len(data) == len(sections) == len(statements), 'Incomplete metadata snapshot'
    assert data['transaction'] == [{'database': database, 'read_only': 'on'}], 'Read-only transaction not proved'
    return data


def metadata_queries():
    models = "SELECT id FROM ir_model WHERE model LIKE 'hr.contract.salary.%' OR model='hr.payroll.structure.type'"
    fields = "SELECT id FROM ir_model_fields WHERE model LIKE 'hr.contract.salary.%' OR relation LIKE 'hr.contract.salary.%' OR (model='hr.payroll.structure.type' AND name='salary_benefits_ids')"
    return {
        'transaction': "SELECT current_database() AS database,current_setting('transaction_read_only') AS read_only",
        'modules': "SELECT name,latest_version,license,state FROM ir_module_module WHERE name IN ('hr_payroll','payroll','hr_contract','hr_contract_salary','hr_contract_salary_payroll','hr_contract_salary_holidays','l10n_cl_simpledigital_payroll') ORDER BY name",
        'models': "SELECT id,model,state,to_jsonb(m)->'transient' AS transient FROM ir_model m WHERE id IN (" + models + ') ORDER BY model',
        'fields': "SELECT id,model,name,ttype,relation,relation_field,required,readonly,store,related,company_dependent,translate,on_delete,"
            "to_jsonb(f)->'relation_table' AS relation_table FROM ir_model_fields f WHERE id IN (" + fields + ') ORDER BY model,name',
        'field_groups': 'SELECT field_id,group_id FROM ir_model_fields_group_rel WHERE field_id IN (' + fields + ') ORDER BY field_id,group_id',
        'selections': 'SELECT field_id,value,sequence FROM ir_model_fields_selection WHERE field_id IN (' + fields + ') ORDER BY field_id,sequence,value',
        'xmlids': "SELECT id,module,name,model,res_id,noupdate FROM ir_model_data WHERE model LIKE 'hr.contract.salary.%' OR (model='ir.model' AND res_id IN (" + models + ")) OR (model='ir.model.fields' AND res_id IN (" + fields + ')) ORDER BY module,name',
        'acl': 'SELECT id,model_id,group_id,active,perm_read,perm_write,perm_create,perm_unlink FROM ir_model_access WHERE model_id IN (' + models + ') ORDER BY model_id,id',
        'record_rules': 'SELECT id,model_id,active,global,domain_force,perm_read,perm_write,perm_create,perm_unlink FROM ir_rule WHERE model_id IN (' + models + ') ORDER BY model_id,id',
        'rule_groups': 'SELECT rule_group_id,group_id FROM rule_group_rel WHERE rule_group_id IN (SELECT id FROM ir_rule WHERE model_id IN (' + models + ')) ORDER BY rule_group_id,group_id',
        'group_aliases': "SELECT id,module,name,res_id,noupdate FROM ir_model_data WHERE model='res.groups' AND res_id IN ("
            'SELECT group_id FROM ir_model_access WHERE model_id IN (' + models + ') UNION SELECT group_id FROM ir_model_fields_group_rel WHERE field_id IN (' + fields + ') '
            'UNION SELECT group_id FROM rule_group_rel WHERE rule_group_id IN (SELECT id FROM ir_rule WHERE model_id IN (' + models + '))) ORDER BY module,name',
        'views': "SELECT id,model,type,inherit_id,active,key,encode(sha256(convert_to(arch_db::text,'UTF8')),'hex') AS architecture_sha256 FROM ir_ui_view WHERE model LIKE 'hr.contract.salary.%' OR arch_db::text LIKE '%salary_benefits_ids%' ORDER BY id",
        'actions': "SELECT id,res_model,view_mode FROM ir_act_window WHERE res_model LIKE 'hr.contract.salary.%' ORDER BY id",
        'tables': "SELECT c.relname,c.relkind FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND c.relkind IN ('r','p') AND c.relname LIKE 'hr_contract_salary_%' ORDER BY c.relname",
        'columns': "SELECT table_name,column_name,data_type,is_nullable FROM information_schema.columns WHERE table_schema='public' AND (table_name LIKE 'hr_contract_salary_%' OR table_name IN ('hr_contract','hr_payslip','hr_payroll_structure')) ORDER BY table_name,ordinal_position",
        'constraints': "SELECT c.oid,r.relname AS table_name,c.conname,c.contype,c.convalidated,pg_get_constraintdef(c.oid) AS definition FROM pg_constraint c JOIN pg_class r ON r.oid=c.conrelid JOIN pg_namespace n ON n.oid=r.relnamespace WHERE n.nspname='public' AND (r.relname LIKE 'hr_contract_salary_%' OR c.confrelid IN (SELECT oid FROM pg_class WHERE relname LIKE 'hr_contract_salary_%')) ORDER BY r.relname,c.conname",
    }


def usage_queries(metadata):
    result = {'transaction': "SELECT current_database() AS database,current_setting('transaction_read_only') AS read_only"}
    columns = {}
    for row in metadata['columns']:
        columns.setdefault(row['table_name'], {})[row['column_name']] = row['data_type']
    for row in metadata['tables']:
        name = row['relname']
        assert name.startswith(TABLE_PREFIX), 'Unexpected salary table family'
        table = identifier(name)
        result['table:' + name] = "SELECT count(*) AS rows,encode(sha256(convert_to(coalesce(string_agg(to_jsonb(t)::text,E'\\n' ORDER BY to_jsonb(t)::text),''),'UTF8')),'hex') AS rows_sha256 FROM " + table + ' t'
        if 'id' in columns[name]:
            result['ids:' + name] = 'SELECT id FROM ' + table + ' ORDER BY id'
        if 'structure_type_id' in columns[name]:
            result['types:' + name] = 'SELECT structure_type_id,count(*) AS rows FROM ' + table + ' GROUP BY structure_type_id ORDER BY structure_type_id'
        # These are technical contract-field names, never amounts or labels.
        reference_fields = [field for field in ('field', 'cost_field') if columns[name].get(field) in ('character varying', 'text')]
        if reference_fields:
            values = ','.join("CASE WHEN " + identifier(field) + " ~ '^[a-z_][a-z0-9_]*$' THEN " + identifier(field) + ' END AS ' + identifier(field) for field in reference_fields)
            result['contract-field-references:' + name] = 'SELECT DISTINCT ' + values + ' FROM ' + table
    if {'structure_type_id', 'state'} <= columns.get('hr_contract', {}).keys():
        result['contract_type_usage'] = 'SELECT structure_type_id,state,count(*) AS rows FROM hr_contract GROUP BY structure_type_id,state ORDER BY structure_type_id,state'
    if {'struct_id', 'state', 'paid'} <= columns.get('hr_payslip', {}).keys() and 'type_id' in columns.get('hr_payroll_structure', {}):
        result['payslip_type_usage'] = 'SELECT s.type_id,p.state,p.paid,count(*) AS rows FROM hr_payslip p JOIN hr_payroll_structure s ON s.id=p.struct_id GROUP BY s.type_id,p.state,p.paid ORDER BY s.type_id,p.state,p.paid'
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', choices=sorted(DATABASES), required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    assert os.geteuid() == 0
    target = args.output.resolve()
    assert target.parent.is_dir() and Path('/opt/steps-validation') in target.parents and not target.exists()
    before = snapshot(args.database, metadata_queries())
    usage = snapshot(args.database, usage_queries(before))
    after = snapshot(args.database, metadata_queries())
    assert before == after, 'Metadata changed during the read-only audit'
    report = {'schema': 1, 'database': args.database, 'read_only': True, 'orm_loaded': False,
        'source_bodies_exported': False, 'salary_amounts_exported': False, 'rules_evaluated': False,
        'database_writes': False, 'runtime_model_table_mapping_certified': False,
        'functional_benefit_engine_certified': False, 'metadata_before': before, 'metadata_after': after,
        'metadata_captures_equal': True, 'usage': usage,
        'tool_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as stream:
        json.dump(report, stream, indent=2)
    print(json.dumps({'database': args.database, 'read_only': True,
        'salary_family_models': len([row for row in before['models'] if row['model'].startswith(PREFIX)]),
        'salary_family_tables': len(before['tables']), 'metadata_equal': True,
        'benefit_rows': {name: value[0]['rows'] for name, value in usage.items() if name.startswith('table:')},
        'evidence_sha256': hashlib.sha256(target.read_bytes()).hexdigest()}))


if __name__ == '__main__':
    main()
