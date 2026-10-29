"""Materialize four original related values on a NEW private SyS clone, SQL only.

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
    args=parser.parse_args()
    assert os.geteuid()==0
    root=args.root.resolve()
    assert str(root).startswith('/opt/steps-validation/') and not root.exists()
    assert re.fullmatch('MANAGEMENT_QA_SYS_PAYROLL_STORAGE_[A-Za-z0-9_]+',args.database)
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
                projection=materialize(cur)
                originals={table:proof['original_columns'] for table,proof in projection.items()}
                after=snapshot(cur,originals)
                assert before==after,'Original data/IDs/metadata/ACL/amounts/counters changed'
                again=materialize(cur)
                assert all(again[table]['projection_sha256']==proof['projection_sha256'] for table,proof in projection.items())
                assert snapshot(cur,originals)==before,'Repeated preparation changed original data'
                dump('original-after',after);dump('relations',projection)
        with connect(args.database) as conn:
            with conn.cursor() as cur:assert snapshot(cur,originals)==before
        dump('storage-after',capacity(pg_directory))
        dump('passed',{'database':args.database,'source':'SyS','original_contracts_preserved':len(before),
            'tables':projection,'backup_decoded':True,'backup_sha256':backup_sha,
            'tool_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'original_metadata_preserved':True,'original_input_null_labels_preserved':True,
            'idempotence_verified':True,'writes_to_source':False,'orm_loaded':False,
            'paid_payroll_recomputed':False,'engine_converted':False,'financial_certified':False})
        print('PAYROLL_RELATED_STORAGE_OK',flush=True)


if __name__=='__main__':main()
