"""Compare every public table and sequence on two native restorations of one SyS dump."""
import argparse
from contextlib import closing
import fcntl
import json
import os
from pathlib import Path
import re

import psycopg2
from psycopg2 import sql

from custody_sys_previred_filestore import digest
from restore_sys_previred_pair import LOCK, require


def snapshot(database, required_nonempty=None):
    with closing(psycopg2.connect(dbname=database, user='postgres', host='/var/run/postgresql')) as conn:
        conn.set_session(readonly=True, isolation_level='REPEATABLE READ')
        with conn.cursor() as cr:
            cr.execute("SET LOCAL search_path=pg_catalog,public")
            cr.execute("SET LOCAL TIME ZONE 'UTC'")
            cr.execute("SELECT current_database(),current_setting('transaction_read_only')")
            require(cr.fetchone() == (database, 'on'), 'wrong-private-restore-transaction')
            cr.execute("""
                SELECT c.relname,c.relkind,pg_get_userbyid(c.relowner),c.relacl::text
                FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
                WHERE n.nspname='public' AND c.relkind IN ('r','p','S')
                ORDER BY c.relname
            """)
            relations = cr.fetchall()
            rows, sequences, definitions = {}, {}, {}
            for name, kind, owner, acl in relations:
                relation = sql.Identifier('public', name)
                definitions[name] = [kind, owner, acl]
                if kind == 'S':
                    cr.execute(sql.SQL("SELECT last_value,is_called FROM {}").format(relation))
                    sequences[name] = list(cr.fetchone())
                else:
                    # The ordered multiset includes duplicate rows and tables without a PK.
                    cr.execute(sql.SQL("""
                        SELECT count(*),encode(sha256(convert_to(coalesce(string_agg(h,'' ORDER BY h),''),
                              'UTF8')),'hex') FROM (SELECT encode(sha256(convert_to(to_jsonb(r)::text,
                              'UTF8')),'hex') AS h FROM ONLY {} r) original
                    """).format(relation))
                    rows[name] = list(cr.fetchone())
            cr.execute("""
                SELECT c.relname, a.attname, format_type(a.atttypid,a.atttypmod), a.attnotnull,
                       a.attidentity,a.attgenerated,pg_get_expr(d.adbin,d.adrelid)
                FROM pg_attribute a JOIN pg_class c ON c.oid=a.attrelid
                JOIN pg_namespace n ON n.oid=c.relnamespace
                LEFT JOIN pg_attrdef d ON d.adrelid=c.oid AND d.adnum=a.attnum
                WHERE n.nspname='public' AND c.relkind IN ('r','p') AND a.attnum>0 AND NOT a.attisdropped
                ORDER BY c.relname,a.attnum
            """)
            columns = {f'{r[0]}.{r[1]}': list(r[2:]) for r in cr.fetchall()}
            cr.execute("""
                SELECT c.relname,k.conname,pg_get_constraintdef(k.oid),k.convalidated FROM pg_constraint k
                JOIN pg_class c ON c.oid=k.conrelid JOIN pg_namespace n ON n.oid=c.relnamespace
                WHERE n.nspname='public' ORDER BY c.relname,k.conname
            """)
            constraints = {f'{r[0]}.{r[1]}':list(r[2:]) for r in cr.fetchall()}
            cr.execute("""SELECT sequencename,data_type::text,start_value,min_value,max_value,increment_by,cycle,cache_size
                          FROM pg_sequences WHERE schemaname='public' ORDER BY sequencename""")
            settings = {r[0]: list(r[1:]) for r in cr.fetchall()}
    if required_nonempty is None:
        anchor = 'hr_payslip'
        if database.startswith(('COMMUNITY_PAYROLL_CERRO_REVIEW_', 'COMMUNITY_CERRO_PAYROLL_RECOVERY_')):
            anchor = 'purchase_order'
        if database.startswith('COMMUNITY_STEPS_CRM_'):
            anchor = 'crm_lead'
        required_nonempty = (anchor, 'ir_attachment')
    require(sequences and all(name in rows and rows[name][0] for name in required_nonempty),
            'expected-full-business-data')
    return {'public_tables':rows,'sequence_values':sequences,'sequence_definitions':settings,
            'relation_owner_and_acl':definitions,'columns':columns,'constraints':constraints}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--control-receipt', type=Path, required=True)
    parser.add_argument('--dump', type=Path, required=True)
    parser.add_argument('--restored', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    os.umask(0o077)
    receipt = json.loads(args.control_receipt.read_bytes())
    control = receipt['snapshot']['database']
    require(re.fullmatch(r'COMMUNITY_SYS_PREVIRED_[A-Z0-9_]+', control)
            and re.fullmatch(r'MANAGEMENT_QA_SYS_PREVIRED_[A-Z0-9_]+', args.restored)
            and receipt['stage'] == 'candidate-restored' and receipt['preserved'], 'private-sys-restores-required')
    with open(LOCK, 'rb') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        backup_sha = digest(args.dump)
        require(receipt['backup_sha256'] == backup_sha, 'expected-sealed-sql-dump')
        before, after = snapshot(control), snapshot(args.restored)
        differences = {section: sorted(key for key in before[section].keys() | after[section].keys()
                                       if before[section].get(key) != after[section].get(key))
                       for section in before}
        result = {'source_dump_sha256':backup_sha, 'control':control, 'restored':args.restored,
                  'counts':{k:len(v) for k,v in before.items()},'differences':differences,
                  'compared_rows':sum(v[0] for v in before['public_tables'].values()),
                  'matches':not any(differences.values())}
        with args.output.open('x',encoding='utf-8') as stream:
            json.dump(result, stream, indent=2)
        print(json.dumps(result['counts']), result['matches'], flush=True)
        require(result['matches'], 'restoration-differs-see-private-receipt')


if __name__ == '__main__':
    main()
