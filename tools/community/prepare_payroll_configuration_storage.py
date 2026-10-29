"""Prepare OCA configuration relations on a NEW Cerro clone, preserving all source rows.

No ORM, engine switch, ACL/metadata rewrite, default owner, salary computation
or external emission. The original structure_id relation remains authoritative.
"""
import argparse
import configparser
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

from psycopg2 import sql
from validate_payroll_relation_storage import connect


FIELDS = {
    ('hr_payroll_structure', 'company_id'): ('hr.payroll.structure', 'res_company'),
    ('hr_payroll_structure', 'parent_id'): ('hr.payroll.structure', 'hr_payroll_structure'),
    ('hr_salary_rule', 'company_id'): ('hr.salary.rule', 'res_company'),
    ('hr_salary_rule', 'parent_rule_id'): ('hr.salary.rule', 'hr_salary_rule'),
    ('hr_salary_rule_category', 'company_id'): ('hr.salary.rule.category', 'res_company'),
}
RELATION = 'hr_structure_salary_rule_rel'
ACTIONS = {'r': 'RESTRICT', 'n': 'SET NULL', 'c': 'CASCADE'}


def schema(cur):
    cur.execute("SELECT c.relname,a.attname FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
                "JOIN pg_attribute a ON a.attrelid=c.oid WHERE n.nspname='public' AND c.relkind IN ('r','p') "
                "AND a.attnum>0 AND NOT a.attisdropped ORDER BY c.relname,a.attnum")
    result = {}
    for table, column in cur.fetchall(): result.setdefault(table, []).append(column)
    return result


def snapshot(cur, originals):
    result = {}
    current = schema(cur)
    for table, names in originals.items():
        assert set(names) <= set(current[table]), 'Original columns missing'
        extra = set(current[table]) - set(names)
        assert extra <= {column for owner, column in FIELDS if owner == table}, 'Unexpected schema mutation'
        expr = sql.SQL('to_jsonb(t)')
        for column in sorted(extra): expr = sql.SQL('({} - {})').format(expr, sql.Literal(column))
        cur.execute(sql.SQL("SELECT count(*),md5(coalesce(string_agg(j::text,E'\\n' ORDER BY j::text),'')) "
            "FROM (SELECT {} j FROM {} t) s").format(expr, sql.Identifier(table)))
        result[table] = cur.fetchone()
    cur.execute("SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
                "WHERE n.nspname='public' AND c.relkind='S' ORDER BY c.relname")
    for (name,) in cur.fetchall():
        cur.execute(sql.SQL('SELECT last_value,is_called FROM {}').format(sql.Identifier(name)))
        result[name] = cur.fetchone()
    return result


def constraints(cur):
    cur.execute("SELECT oid,conrelid::regclass::text,conname,pg_get_constraintdef(oid),convalidated "
                "FROM pg_constraint WHERE connamespace='public'::regnamespace ORDER BY oid")
    return {str(row[0]): list(row[1:]) for row in cur.fetchall()}


def community_contract(cur):
    cur.execute("SELECT count(*) FROM ir_module_module WHERE state='installed' AND license='OEEL-1'")
    assert not cur.fetchone()[0]
    cur.execute("SELECT name,latest_version FROM ir_module_module WHERE name IN ('payroll','step_payroll_oca_api') AND state='installed'")
    versions = dict(cur.fetchall()); assert set(versions) == {'payroll', 'step_payroll_oca_api'}
    result = {'versions': versions, 'fields': [], 'relation': [], 'read_only': True, 'orm_loaded': False}
    for (table, name), (model, target) in FIELDS.items():
        cur.execute("SELECT attnotnull,format_type(atttypid,atttypmod),atthasdef FROM pg_attribute "
                    "WHERE attrelid=%s::regclass AND attname=%s AND NOT attisdropped", (table, name))
        assert cur.fetchone() == (False, 'integer', False), 'Reference field must be nullable with no SQL default'
        cur.execute("SELECT store,required,related,ttype FROM ir_model_fields WHERE model=%s AND name=%s", (model, name))
        assert cur.fetchone() == (True, False, None, 'many2one')
        cur.execute("SELECT c.confdeltype,c.confrelid::regclass::text,c.convalidated FROM pg_constraint c "
                    "JOIN pg_attribute a ON a.attrelid=c.conrelid AND a.attnum=c.conkey[1] "
                    "WHERE c.contype='f' AND c.conrelid=%s::regclass AND a.attname=%s", (table, name))
        rows = cur.fetchall(); assert len(rows) == 1 and rows[0][1:] == (target, True)
        assert rows[0][0] in ACTIONS
        result['fields'].append({'table': table, 'column': name, 'target': target, 'ondelete': ACTIONS[rows[0][0]]})
    cur.execute("SELECT attname,attnotnull,format_type(atttypid,atttypmod) FROM pg_attribute "
                "WHERE attrelid=%s::regclass AND attnum>0 AND NOT attisdropped ORDER BY attname", (RELATION,))
    assert cur.fetchall() == [('rule_id', True, 'integer'), ('struct_id', True, 'integer')]
    cur.execute("SELECT c.confdeltype,c.confrelid::regclass::text,a.attname,c.convalidated FROM pg_constraint c "
                "JOIN pg_attribute a ON a.attrelid=c.conrelid AND a.attnum=c.conkey[1] WHERE c.contype='f' "
                "AND c.conrelid=%s::regclass ORDER BY a.attname", (RELATION,))
    assert cur.fetchall() == [('c', 'hr_salary_rule', 'rule_id', True), ('c', 'hr_payroll_structure', 'struct_id', True)]
    result['relation'] = ['struct_id', 'rule_id']
    return result


def prepare(cur, contract, owner):
    cur.execute('LOCK TABLE hr_payroll_structure,hr_salary_rule,hr_salary_rule_category IN SHARE ROW EXCLUSIVE MODE')
    for field in contract['fields']:
        table, column = field['table'], field['column']
        cur.execute(sql.SQL('ALTER TABLE {} ADD COLUMN IF NOT EXISTS {} integer').format(sql.Identifier(table), sql.Identifier(column)))
        cur.execute(sql.SQL('SELECT count(*) FROM {} WHERE {} IS NOT NULL').format(sql.Identifier(table), sql.Identifier(column)))
        assert not cur.fetchone()[0], 'Never infer a company owner or parent'
        name = table + '_' + column + '_fkey'
        cur.execute("SELECT pg_get_constraintdef(oid),convalidated FROM pg_constraint WHERE conrelid=%s::regclass AND conname=%s", (table, name))
        found = cur.fetchall()
        expected = 'FOREIGN KEY (%s) REFERENCES %s(id) ON DELETE %s' % (column, field['target'], field['ondelete'])
        if found: assert found == [(expected, True)]
        else:
            cur.execute(sql.SQL('ALTER TABLE {} ADD CONSTRAINT {} FOREIGN KEY ({}) REFERENCES {}(id) ON DELETE {} NOT VALID').format(
                sql.Identifier(table), sql.Identifier(name), sql.Identifier(column), sql.Identifier(field['target']), sql.SQL(field['ondelete'])))
            cur.execute(sql.SQL('ALTER TABLE {} VALIDATE CONSTRAINT {}').format(sql.Identifier(table), sql.Identifier(name)))
    cur.execute(sql.SQL('CREATE TABLE IF NOT EXISTS {} (struct_id integer NOT NULL REFERENCES hr_payroll_structure(id) ON DELETE CASCADE, '
                        'rule_id integer NOT NULL REFERENCES hr_salary_rule(id) ON DELETE CASCADE, UNIQUE(struct_id,rule_id))').format(sql.Identifier(RELATION)))
    cur.execute(sql.SQL('ALTER TABLE {} OWNER TO {}').format(sql.Identifier(RELATION), sql.Identifier(owner)))
    cur.execute('SELECT struct_id,id FROM hr_salary_rule ORDER BY struct_id,id')
    original = cur.fetchall(); assert all(struct for struct, rule in original)
    cur.execute(sql.SQL('SELECT struct_id,rule_id FROM {} ORDER BY struct_id,rule_id').format(sql.Identifier(RELATION)))
    existing = cur.fetchall(); assert not existing or existing == original, 'Existing relation needs explicit review'
    if not existing:
        cur.execute(sql.SQL('INSERT INTO {} (struct_id,rule_id) SELECT struct_id,id FROM hr_salary_rule').format(sql.Identifier(RELATION)))
    cur.execute(sql.SQL('SELECT struct_id,rule_id FROM {} ORDER BY struct_id,rule_id').format(sql.Identifier(RELATION)))
    assert cur.fetchall() == original
    return {'memberships': len(original), 'sha256': hashlib.sha256(json.dumps(original).encode()).hexdigest(),
            'company_or_parent_values_assigned': 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--database', required=True)
    parser.add_argument('--community-database', required=True)
    args = parser.parse_args()
    assert os.geteuid() == 0
    assert re.fullmatch(r'MANAGEMENT_QA_CERRO_CONFIG_STORAGE_[A-Za-z0-9_]+', args.database)
    assert re.fullmatch(r'COMMUNITY_PAYROLL_API_[A-Za-z0-9_]+', args.community_database)
    root = args.root.resolve(); assert Path('/opt/steps-validation') in root.parents and not root.exists()
    root.mkdir(mode=0o700)
    config = configparser.ConfigParser(interpolation=None); assert config.read('/etc/odoo18-cerroelplomo.conf')
    assert config['options']['db_name'] == 'CERRO_EL_PLOMO'
    def run(*cmd, **kw): return subprocess.run(cmd, check=True, **kw)
    def dump(name, value): (root / (name + '.json')).write_text(json.dumps(value, indent=2, default=str))
    with open('/run/lock/steps-environments.lock', 'a') as lease:
        fcntl.flock(lease, fcntl.LOCK_EX)
        with connect('postgres') as conn, conn.cursor() as cur:
            cur.execute('SELECT 1 FROM pg_database WHERE datname=%s', (args.database,)); assert not cur.fetchone()
            cur.execute('SHOW data_directory'); pgdir = cur.fetchone()[0]
            for path, minimum in ((Path(pgdir), 5 * 1024**3), (root, 2 * 1024**3)):
                stats = os.statvfs(path); assert stats.f_bavail * stats.f_frsize > minimum + 1024**3
        with connect(args.community_database) as conn, conn.cursor() as cur:
            cur.execute('SET TRANSACTION READ ONLY'); contract = community_contract(cur); dump('community-contract', contract)
        backup = root / 'source.dump'
        with backup.open('wb') as out: run('sudo', '-u', 'postgres', 'pg_dump', '-Fc', 'CERRO_EL_PLOMO', stdout=out)
        with backup.open('rb') as inp, (root / 'decode.log').open('wb') as out:
            run('sudo', '-u', 'postgres', 'pg_restore', '--file=/dev/null', stdin=inp, stdout=out, stderr=subprocess.STDOUT)
        run('sudo', '-u', 'postgres', 'createdb', '--owner=' + config['options']['db_user'], args.database)
        with backup.open('rb') as inp, (root / 'restore.log').open('wb') as out:
            run('sudo', '-u', 'postgres', 'pg_restore', '--exit-on-error', '--no-owner', '--no-acl', '--no-comments',
                '--role=' + config['options']['db_user'], '-d', args.database, stdin=inp, stdout=out, stderr=subprocess.STDOUT)
        with connect(args.database) as conn, conn.cursor() as cur:
            cur.execute('UPDATE ir_cron SET active=false; UPDATE ir_mail_server SET active=false')
        with connect(args.database) as conn, conn.cursor() as cur:
            cur.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE')
            original_columns = schema(cur); original_constraints = constraints(cur)
            before = snapshot(cur, original_columns); dump('original-before', before)
            proof = prepare(cur, contract, config['options']['db_user'])
            after = snapshot(cur, original_columns); assert before == after
            current_constraints = constraints(cur)
            assert {k: current_constraints.get(k) for k in original_constraints} == original_constraints
            assert prepare(cur, contract, config['options']['db_user']) == proof
            assert snapshot(cur, original_columns) == before
            dump('original-after', after); dump('columns-before', original_columns); dump('relations', proof)
        with connect(args.database) as conn, conn.cursor() as cur:
            assert snapshot(cur, original_columns) == before
            assert prepare(cur, contract, config['options']['db_user']) == proof
        dump('passed', dict(proof, database=args.database, original_contracts_preserved=len(before),
            backup_decoded=True, backup_sha256=hashlib.sha256(backup.read_bytes()).hexdigest(),
            tool_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), idempotence_verified=True,
            original_metadata_preserved=True, orm_loaded=False, engine_converted=False, financial_certified=False,
            writes_to_source=False, paid_payroll_recomputed=False))
        print('PAYROLL_CONFIGURATION_STORAGE_OK ' + str(proof['memberships']))


if __name__ == '__main__': main()
