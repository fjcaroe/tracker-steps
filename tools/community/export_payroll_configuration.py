"""Seal original payroll configuration privately, without evaluating a rule.

This is a source capsule, not an importer or an engine conversion. Raw JSON
rows preserve company-dependent JSON, SQL NULLs and original configuration IDs.
Formula bodies are private business data and must never be printed or committed.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re

from psycopg2 import sql
from validate_payroll_relation_storage import connect


TABLES = {
    'hr_salary_rule_category': 'hr.salary.rule.category',
    'hr_payroll_structure_type': 'hr.payroll.structure.type',
    'hr_payroll_structure': 'hr.payroll.structure',
    'hr_salary_rule': 'hr.salary.rule',
    'hr_payslip_input_type': 'hr.payslip.input.type',
}


def seal(cursor):
    cursor.execute('SHOW transaction_read_only')
    assert cursor.fetchone()[0] == 'on'
    cursor.execute("""SELECT c.conrelid::regclass::text,a.attname,
        c.confrelid::regclass::text,b.attname,c.convalidated,c.confdeltype
        FROM pg_constraint c JOIN pg_attribute a ON a.attrelid=c.conrelid AND a.attnum=c.conkey[1]
        JOIN pg_attribute b ON b.attrelid=c.confrelid AND b.attnum=c.confkey[1]
        WHERE c.contype='f' AND array_length(c.conkey,1)=1 AND c.connamespace='public'::regnamespace
        ORDER BY c.conrelid::regclass::text,a.attname""")
    foreign_keys = [dict(zip(('table', 'column', 'target', 'target_column', 'validated', 'ondelete'), row))
                    for row in cursor.fetchall()]
    cursor.execute("SELECT table_name FROM information_schema.columns WHERE table_schema='public' AND column_name='id'")
    has_id = {row[0] for row in cursor.fetchall()}
    relation_candidates = {row['table'] for row in foreign_keys if row['target'] in TABLES}
    relations = sorted(table for table in relation_candidates if table not in TABLES and table not in has_id
        and all(row['target'] in TABLES for row in foreign_keys if row['table'] == table))
    selected = set(TABLES) | set(relations)
    result = {'schema': 1, 'read_only': True, 'database': cursor.connection.info.dbname,
        'orm_loaded': False, 'rules_evaluated': False, 'historical_payroll_read': False,
        'engine_converted': False, 'financial_certified': False, 'import_authorized_by_capsule': False,
        'tables': {}, 'external_references': {}, 'relations': relations}
    for table in sorted(selected):
        cursor.execute("""SELECT attname,format_type(atttypid,atttypmod),attnotnull
            FROM pg_attribute WHERE attrelid=%s::regclass AND attnum>0 AND NOT attisdropped ORDER BY attnum""", (table,))
        columns = [dict(zip(('name', 'pg_type', 'not_null'), row)) for row in cursor.fetchall()]
        order = sql.Identifier('id') if table in has_id else sql.SQL('to_jsonb(t)::text')
        cursor.execute(sql.SQL('SELECT to_jsonb(t)::text FROM {} t ORDER BY {}').format(sql.Identifier(table), order))
        rows = [row[0] for row in cursor.fetchall()]
        result['tables'][table] = {'model': TABLES.get(table), 'columns': columns,
            'row_count': len(rows), 'rows_json': rows,
            'rows_sha256': hashlib.sha256('\n'.join(rows).encode()).hexdigest(),
            'foreign_keys': [row for row in foreign_keys if row['table'] == table]}
        for fk in result['tables'][table]['foreign_keys']:
            assert fk['validated'], 'Unvalidated original configuration relation'
            if fk['target'] in selected:
                continue
            cursor.execute(sql.SQL('SELECT DISTINCT {} FROM {} WHERE {} IS NOT NULL ORDER BY 1').format(
                sql.Identifier(fk['column']), sql.Identifier(table), sql.Identifier(fk['column'])))
            ids = [row[0] for row in cursor.fetchall()]
            cursor.execute(sql.SQL('SELECT count(*) FROM {} WHERE {}=ANY(%s)').format(
                sql.Identifier(fk['target']), sql.Identifier(fk['target_column'])), (ids,))
            assert cursor.fetchone()[0] == len(ids), 'Missing original referenced master'
            result['external_references'][table + '.' + fk['column']] = {'target': fk['target'],
                'target_column': fk['target_column'], 'ids': ids, 'target_adopted': False}
    cursor.execute("""SELECT id,module,name,model,res_id,noupdate FROM ir_model_data
        WHERE model=ANY(%s) ORDER BY id""", (list(TABLES.values()),))
    result['xmlids'] = [dict(zip(('id', 'module', 'name', 'model', 'res_id', 'noupdate'), row)) for row in cursor.fetchall()]
    cursor.execute("""SELECT model,name,ttype,relation,required,readonly,store,related,company_dependent
        FROM ir_model_fields WHERE model=ANY(%s) ORDER BY model,name""", (list(TABLES.values()),))
    result['field_metadata'] = [dict(zip(('model', 'name', 'type', 'relation', 'required', 'readonly',
        'store', 'related', 'company_dependent'), row)) for row in cursor.fetchall()]
    for row in result['xmlids']:
        table = next(table for table, model in TABLES.items() if model == row['model'])
        assert row['res_id'] in {json.loads(value)['id'] for value in result['tables'][table]['rows_json']}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    assert os.geteuid() == 0
    assert re.fullmatch(r'MANAGEMENT_QA_CERRO_PAYROLL_API_[A-Za-z0-9_]+', args.database)
    assert Path('/opt/steps-validation') in args.output.resolve().parents
    assert not args.output.exists() and args.output.parent.is_dir()
    with connect(args.database) as conn:
        conn.set_session(readonly=True, isolation_level='REPEATABLE READ')
        with conn.cursor() as cursor:
            result = seal(cursor)
    encoded = json.dumps(result, indent=2, ensure_ascii=False, default=str).encode()
    fd = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(encoded)
        stream.flush()
        os.fsync(stream.fileno())
    reread = args.output.read_bytes()
    assert reread == encoded
    print(json.dumps({'capsule_sha256': hashlib.sha256(encoded).hexdigest(),
        'configuration_rows': {name: row['row_count'] for name, row in result['tables'].items()},
        'xmlids': len(result['xmlids']), 'read_only': True, 'engine_converted': False}))


if __name__ == '__main__':
    main()
