"""Prepare original related values and optional real OCA FKs on a new SyS clone.

This is storage preparation, not an engine switch or a financial certification.
Never import Odoo: closed payroll amounts and computations remain untouched.
"""
import argparse
import configparser
import fcntl
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import subprocess

import psycopg2
from psycopg2 import sql


RELATIONS = (
    ('hr_payslip_worked_days', 'hr_work_entry_type', 'work_entry_type_id'),
    ('hr_payslip_input', 'hr_payslip_input_type', 'input_type_id'),
)


def foreign_keys(cursor):
    cursor.execute("SELECT oid,conrelid::regclass::text,conname,pg_get_constraintdef(oid),convalidated "
        "FROM pg_constraint WHERE contype='f' AND conrelid IN "
        "('hr_payslip_worked_days'::regclass,'hr_payslip_input'::regclass) ORDER BY oid")
    return [dict(zip(('oid','table','name','definition','validated'),row)) for row in cursor.fetchall()]


def community_contract(cursor):
    """Admit the actual installed engine's contract, without ORM or demo rules."""
    cursor.execute("SELECT name,latest_version FROM ir_module_module WHERE state='installed' "
                   "AND name IN ('payroll','step_payroll_oca_api') ORDER BY name")
    versions=dict(cursor.fetchall())
    if set(versions)!={'payroll','step_payroll_oca_api'}:
        raise ValueError('The reference must contain the real OCA engine and API')
    cursor.execute("SELECT count(*) FROM ir_module_module WHERE state='installed' AND license='OEEL-1'")
    if cursor.fetchone()[0]:raise ValueError('The target reference must have zero Enterprise')
    cursor.execute("SELECT id,model,name,ttype,relation,store,required,on_delete,related FROM ir_model_fields "
        "WHERE model IN ('hr.payslip.worked_days','hr.payslip.input') "
        "AND name IN ('code','contract_id') ORDER BY model,name")
    rows=[dict(zip(('id','model','name','type','relation','store','required','on_delete','related'),row))
          for row in cursor.fetchall()]
    if len(rows)!=4:raise ValueError('Missing actual related-storage target fields')
    for row in rows:
        if not row['store'] or not row['required'] or row['related']:
            raise ValueError('Unexpected target storage attributes')
        expected=('char',None,None) if row['name']=='code' else ('many2one','hr.contract','restrict')
        if (row['type'],row['relation'],row['on_delete'])!=expected:
            raise ValueError('Unexpected target relation semantics')
    constraints=foreign_keys(cursor)
    for table,_,_ in RELATIONS:
        expected='FOREIGN KEY (contract_id) REFERENCES hr_contract(id) ON DELETE RESTRICT'
        matches=[row for row in constraints if row['table']==table and row['name']==table+'_contract_id_fkey']
        if len(matches)!=1 or matches[0]['definition']!=expected or not matches[0]['validated']:
            raise ValueError('Actual Community contract FK is not validated RESTRICT: '+table)
    return {'modules':versions,'fields':rows,'foreign_keys':constraints,'orm_loaded':False,
            'read_only':True,'enterprise':0}


def adopt_contract_foreign_keys(cursor):
    """Enforce two real target relations, never replace a preexisting constraint.

    Native related fields stay nonstored in registry metadata. New SQL columns
    stay nullable until the complete ORM conversion; no historical row changes.
    """
    before=foreign_keys(cursor)
    for table,_,_ in RELATIONS:
        expected='FOREIGN KEY (contract_id) REFERENCES hr_contract(id) ON DELETE RESTRICT'
        name=table+'_contract_id_fkey'
        current=[row for row in before if row['table']==table and
                 (row['name']==name or row['definition'].startswith('FOREIGN KEY (contract_id)'))]
        if current:
            if len(current)!=1 or current[0]['name']!=name or current[0]['definition']!=expected or not current[0]['validated']:
                raise ValueError('Existing contract FK requires explicit review: '+table)
            continue
        cursor.execute(sql.SQL('ALTER TABLE {} ADD CONSTRAINT {} FOREIGN KEY (contract_id) '
            'REFERENCES hr_contract(id) ON DELETE RESTRICT NOT VALID').format(sql.Identifier(table),sql.Identifier(name)))
        cursor.execute(sql.SQL('ALTER TABLE {} VALIDATE CONSTRAINT {}').format(sql.Identifier(table),sql.Identifier(name)))
    after=foreign_keys(cursor)
    indexed={row['oid']:row for row in after}
    if any(indexed.get(row['oid'])!=row for row in before):
        raise ValueError('An original foreign key changed')
    return after


def connect(database):
    """Local peer connection as the existing OS postgres role, no credentials."""
    os.seteuid(pwd.getpwnam('postgres').pw_uid)
    try:return psycopg2.connect(dbname=database,user='postgres')
    finally:os.seteuid(0)


def materialize(cursor):
    """Copy the original related code/contract, refusing conflicts or missing FKs.

    Caller owns the transaction and the private-clone lease. No descriptions,
    monetary values, write dates, metadata or sequences are assigned here.
    """
    cursor.execute('LOCK TABLE hr_payslip,hr_payslip_worked_days,hr_payslip_input,hr_work_entry_type,hr_payslip_input_type,hr_contract IN SHARE ROW EXCLUSIVE MODE')
    proof = {}
    # Audit the complete batch before performing any DDL or data writes.
    for table, master, relation in RELATIONS:
        cursor.execute(sql.SQL('SELECT count(*) FROM {} t LEFT JOIN {} m ON m.id=t.{} '
            'LEFT JOIN hr_payslip s ON s.id=t.payslip_id LEFT JOIN hr_contract c ON c.id=s.contract_id '
            'WHERE m.id IS NULL OR nullif(m.code,\'\') IS NULL OR c.id IS NULL '
            'OR c.employee_id IS DISTINCT FROM s.employee_id OR c.company_id IS DISTINCT FROM s.company_id'
        ).format(sql.Identifier(table), sql.Identifier(master), sql.Identifier(relation)))
        if cursor.fetchone()[0]:
            raise ValueError('Missing or conflicting original related master: '+table)
        cursor.execute("SELECT column_name,data_type FROM information_schema.columns WHERE table_schema='public' AND table_name=%s",(table,))
        names=dict(cursor.fetchall())
        for field, dtype in (('code','character varying'),('contract_id','integer')):
            if field in names and names[field]!=dtype:
                raise ValueError('Unexpected existing storage type: '+table+'.'+field)
            if field in names:
                cursor.execute(sql.SQL('SELECT count(*) FROM {} WHERE {} IS NULL').format(sql.Identifier(table),sql.Identifier(field)))
                if cursor.fetchone()[0]:
                    raise ValueError('Existing stored NULL must be reviewed, never silently repaired: '+table+'.'+field)
                expected=sql.SQL('m.code') if field=='code' else sql.SQL('s.contract_id')
                cursor.execute(sql.SQL('SELECT count(*) FROM {} t JOIN {} m ON m.id=t.{} '
                    'JOIN hr_payslip s ON s.id=t.payslip_id WHERE t.{} IS NOT NULL AND t.{} IS DISTINCT FROM {}'
                ).format(sql.Identifier(table),sql.Identifier(master),sql.Identifier(relation),
                         sql.Identifier(field),sql.Identifier(field),expected))
                if cursor.fetchone()[0]:
                    raise ValueError('Existing storage conflicts with original related value: '+table+'.'+field)
        cursor.execute(sql.SQL('SELECT t.id,m.id,m.code,s.contract_id FROM {} t JOIN {} m ON m.id=t.{} '
                              'JOIN hr_payslip s ON s.id=t.payslip_id ORDER BY t.id'
        ).format(sql.Identifier(table),sql.Identifier(master),sql.Identifier(relation)))
        rows=cursor.fetchall()
        proof[table]={'rows':len(rows),'projection_sha256':hashlib.sha256(json.dumps(rows).encode()).hexdigest(),
                      'original_columns':sorted(names)}
    for table, master, relation in RELATIONS:
        for field,dtype in (('code','varchar'),('contract_id','integer')):
            cursor.execute(sql.SQL('ALTER TABLE {} ADD COLUMN IF NOT EXISTS {} '+dtype).format(sql.Identifier(table),sql.Identifier(field)))
        cursor.execute(sql.SQL('UPDATE {} t SET code=m.code,contract_id=s.contract_id FROM {},hr_payslip s '
            'WHERE m.id=t.{} AND s.id=t.payslip_id AND (t.code IS NULL OR t.contract_id IS NULL)'
        ).format(sql.Identifier(table),sql.SQL('{} m').format(sql.Identifier(master)),sql.Identifier(relation)))
        cursor.execute(sql.SQL('SELECT count(*) FROM {} t JOIN {} m ON m.id=t.{} '
            'JOIN hr_payslip s ON s.id=t.payslip_id WHERE t.code IS DISTINCT FROM m.code '
            'OR t.contract_id IS DISTINCT FROM s.contract_id'
        ).format(sql.Identifier(table),sql.Identifier(master),sql.Identifier(relation)))
        if cursor.fetchone()[0]:raise ValueError('Related projection was not retained: '+table)
    return proof


def snapshot(cursor, original_columns=None):
    """Every public table and sequence; ignore only our four extra columns."""
    cursor.execute("SELECT c.relname,c.relkind FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND c.relkind IN ('r','p','S') ORDER BY c.relname")
    tables=cursor.fetchall();result={}
    for table, kind in tables:
        if kind=='S':
            cursor.execute(sql.SQL('SELECT last_value,is_called FROM {}').format(sql.Identifier(table)))
            result[table]={'sequence':cursor.fetchone()};continue
        expression=sql.SQL('to_jsonb(t)')
        if original_columns is not None and table in original_columns:
            added=set(('code','contract_id'))-set(original_columns[table])
            for field in sorted(added):expression=sql.SQL('({} - {})').format(expression,sql.Literal(field))
        cursor.execute(sql.SQL("SELECT count(*),md5(coalesce(string_agg(j::text,E'\\n' ORDER BY j::text),'')) FROM (SELECT {} j FROM {} t) r").format(expression,sql.Identifier(table)))
        count,digest=cursor.fetchone();result[table]={'rows':count,'md5':digest}
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--database',required=True)
    parser.add_argument('--community-database',help='Existing private zero-Enterprise OCA reference; enables FK preparation')
    args=parser.parse_args()
    assert os.geteuid()==0
    root=args.root.resolve()
    assert str(root).startswith('/opt/steps-validation/') and not root.exists()
    assert re.fullmatch('MANAGEMENT_QA_SYS_PAYROLL_STORAGE_[A-Za-z0-9_]+',args.database)
    if args.community_database:
        assert re.fullmatch('COMMUNITY_PAYROLL_API_[A-Za-z0-9_]+',args.community_database)
    config=configparser.ConfigParser(interpolation=None)
    assert config.read('/etc/odoo18-sys.conf') and config['options']['db_name']=='SyS'
    root.mkdir(mode=0o700)
    def dump(name,value):(root/(name+'.json')).write_text(json.dumps(value,indent=2))
    def run(*command,**kw):return subprocess.run(command,check=True,**kw)
    def capacity(pg_directory,required=0):
        result={}
        for name,directory,minimum in (('postgres',pg_directory,5*1024**3),('artifacts',root,2*1024**3)):
            stats=os.statvfs(directory);available=stats.f_bavail*stats.f_frsize
            assert available>=minimum+required,'Storage reserve too low: '+name
            result[name]={'available_bytes':available,'minimum_bytes':minimum,'estimated_extra_bytes':required}
        return result
    with open('/run/lock/steps-environments.lock','a') as lease:
        print('PAYROLL_RELATED_STORAGE_WAITING_FOR_SHARED_LEASE',flush=True)
        fcntl.flock(lease,fcntl.LOCK_EX)
        with connect('postgres') as conn:
            with conn.cursor() as cur:
                cur.execute('SHOW data_directory');pg_directory=cur.fetchone()[0]
                cur.execute('SELECT 1 FROM pg_database WHERE datname=%s',(args.database,));assert not cur.fetchone()
                cur.execute("SELECT pg_database_size('SyS')");estimated=cur.fetchone()[0]*2
        dump('storage-preflight',capacity(pg_directory,estimated))
        if args.community_database:
            with connect(args.community_database) as conn:
                with conn.cursor() as cur:
                    cur.execute('SET TRANSACTION READ ONLY')
                    dump('community-contract',community_contract(cur))
        backup=root/'source.dump'
        with backup.open('wb') as stream:run('sudo','-u','postgres','pg_dump','-Fc','SyS',stdout=stream)
        with backup.open('rb') as stream,(root/'backup-decode.log').open('wb') as log:
            run('sudo','-u','postgres','pg_restore','--file=/dev/null',stdin=stream,stdout=log,stderr=subprocess.STDOUT)
        digest=hashlib.sha256()
        with backup.open('rb') as stream:
            for block in iter(lambda:stream.read(1024*1024),b''):digest.update(block)
        backup_sha=digest.hexdigest()
        run('sudo','-u','postgres','createdb','--owner='+config['options']['db_user'],args.database)
        with backup.open('rb') as stream,(root/'restore.log').open('w') as log:
            run('sudo','-u','postgres','pg_restore','--exit-on-error','--no-owner','--no-acl','--no-comments',
                '--role='+config['options']['db_user'],'-d',args.database,stdin=stream,stdout=log,stderr=subprocess.STDOUT)
        dump('storage-after-restore',capacity(pg_directory))
        with connect(args.database) as conn:
            with conn.cursor() as cur:
                # Only the new clone is isolated. No ORM/server is ever loaded.
                cur.execute('UPDATE ir_cron SET active=false; UPDATE ir_mail_server SET active=false')
        with connect(args.database) as conn:
            with conn.cursor() as cur:
                cur.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE')
                before=snapshot(cur);dump('original-before',before)
                original_foreign_keys=foreign_keys(cur);dump('foreign-keys-before',original_foreign_keys)
                projection=materialize(cur)
                prepared_foreign_keys=adopt_contract_foreign_keys(cur) if args.community_database else foreign_keys(cur)
                originals={table:proof['original_columns'] for table,proof in projection.items()}
                after=snapshot(cur,originals)
                assert before==after,'Original data/IDs/metadata/ACL/amounts/counters changed'
                again=materialize(cur)
                if args.community_database:
                    assert adopt_contract_foreign_keys(cur)==prepared_foreign_keys,'Repeated FK preparation changed identities'
                assert all(again[table]['projection_sha256']==proof['projection_sha256'] for table,proof in projection.items())
                assert snapshot(cur,originals)==before,'Repeated preparation changed original data'
                dump('original-after',after);dump('relations',projection)
                dump('foreign-keys-after',prepared_foreign_keys)
        with connect(args.database) as conn:
            with conn.cursor() as cur:
                assert snapshot(cur,originals)==before
                assert foreign_keys(cur)==prepared_foreign_keys
        dump('storage-after',capacity(pg_directory))
        dump('passed',{'database':args.database,'source':'SyS','original_contracts_preserved':len(before),
            'tables':projection,'backup_decoded':True,'backup_sha256':backup_sha,
            'tool_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'original_metadata_preserved':True,'original_input_null_labels_preserved':True,
            'contract_fks_prepared':bool(args.community_database),'community_reference':args.community_database,
            'original_foreign_keys_preserved':True,'orm_metadata_adopted':False,
            'native_nullability_changed':False,
            'idempotence_verified':True,'writes_to_source':False,'orm_loaded':False,
            'paid_payroll_recomputed':False,'engine_converted':False,'financial_certified':False})
        print('PAYROLL_RELATED_STORAGE_OK',flush=True)


if __name__=='__main__':main()
