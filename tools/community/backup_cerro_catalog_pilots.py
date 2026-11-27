"""Stream private Cerro rehearsal backups and verify physical references under the shared environment lock."""
import argparse
import fcntl
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tarfile

import psycopg2
from psycopg2 import sql

from audit_cerro_original_schema import catalogue,queries

PILOTS={
    'COMMUNITY_CERRO_BOM_CONTRACTS_20261127U44M': Path('/opt/steps-validation/community-cerro-contracts-20261127U44M'),
    'COMMUNITY_CERRO_BOM_CONTRACTS_20261127U44K': Path('/opt/steps-validation/community-cerro-contracts-20261127U44K'),
    'COMMUNITY_CERRO_BOM_PRODUCT_20261126U42P': Path('/opt/steps-validation/community-cerro-studio-product-20261126U42P'),
}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def inventory(db, socket=None, port=None):
    with psycopg2.connect(dbname=db,host=socket or '/var/run/postgresql',port=port or 5432,user='postgres') as conn:
        conn.set_session(readonly=True,isolation_level='REPEATABLE READ')
        with conn.cursor() as cr:
            cr.execute("SET LOCAL search_path=pg_catalog,public")
            cr.execute("SELECT current_database(),current_user,current_setting('transaction_read_only')")
            assert cr.fetchone()==(db,'postgres','on')
            cr.execute("""SELECT n.nspname,c.relname FROM pg_class c JOIN pg_namespace n ON c.relnamespace=n.oid
                WHERE c.relkind IN ('r','p') AND n.nspname NOT LIKE 'pg_%' AND n.nspname<>'information_schema'
                ORDER BY 1,2""")
            tables={}
            for schema,table in cr.fetchall():
                cr.execute(sql.SQL('SELECT to_jsonb(r)::text FROM {} r').format(sql.Identifier(schema,table)))
                hashes=sorted(hashlib.sha256(row[0].encode()).digest() for row in cr)
                tables[schema+'.'+table]=[len(hashes),digest(b''.join(hashes))]
            sections={}
            for kind,query in queries().items():
                names,rows=catalogue(cr,query)
                if kind=='database':
                    # Logical restoration intentionally uses a separate local
                    # tablespace; every other permission and attribute is kept.
                    idx=names.index('tablespace')
                    for values in rows.values():
                        values[idx]='<private tablespace>'
                packed=json.dumps(sorted(rows.items()),separators=(',',':')).encode()
                sections[kind]=[len(rows),digest(packed)]
            cr.execute("""SELECT sequencename,schemaname FROM pg_sequences
                WHERE schemaname NOT LIKE 'pg_%' ORDER BY 1,2""")
            pointers={}
            for sequence,schema in cr.fetchall():
                cr.execute(sql.SQL('SELECT last_value,is_called FROM {}').format(sql.Identifier(schema,sequence)))
                pointers[schema+'.'+sequence]=cr.fetchone()
            cr.execute("""SELECT store_fname,checksum,file_size FROM ir_attachment WHERE store_fname IS NOT NULL
                GROUP BY 1,2,3 ORDER BY 1,2,3""")
            objects={name:[sha,size] for name,sha,size in cr}
            assert all(name==sha[:2]+'/'+sha and len(sha)==40 for name,(sha,size) in objects.items())
            return dict(tables=tables,sections=sections,sequences=pointers,objects=objects)


class Sink:
    def __init__(self):
        self.hash=hashlib.sha256()
        self.size=0

    def write(self,chunk):
        self.hash.update(chunk)
        self.size+=len(chunk)
        return sys.stdout.buffer.write(chunk)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('database',choices=PILOTS)
    parser.add_argument('artifact',choices=['inventory','dump','filestore'])
    args=parser.parse_args()
    with open('/run/lock/steps-environments.lock','rb') as lock:
        fcntl.flock(lock,fcntl.LOCK_SH)
        sink=Sink()
        if args.artifact=='inventory':
            result=subprocess.check_output(['runuser','-u','postgres','--','env',
                'PYTHONPATH='+str(Path(__file__).resolve().parent)+':/opt/steps-validation/community-cerro-studio-strict-20261126U42C/tools',
                '/usr/bin/python3.10','-c','from backup_cerro_catalog_pilots import inventory;import json,sys;print(json.dumps(inventory(sys.argv[1]),sort_keys=True,separators=(",",":")))',args.database])
            sink.write(result)
        elif args.artifact=='dump':
            with subprocess.Popen(['runuser','-u','postgres','--','pg_dump','--no-tablespaces','-Fc','-d',args.database],stdout=subprocess.PIPE) as dump:
                while block:=dump.stdout.read(1024**2):
                    sink.write(block)
                if dump.wait()!=0:
                    raise ValueError('PostgreSQL backup failed')
        else:
            from restore_cerro_studio_strict import references
            base=PILOTS[args.database]/'data/filestore'/args.database
            objects=references(args.database)
            with tarfile.open(fileobj=sink,mode='w|') as tar:
                for name,(sha,size) in objects.items():
                    path=base/name
                    if path.is_symlink() or path.parent.is_symlink() or path.stat().st_size!=size:
                        raise ValueError('Unexpected physical object')
                    with path.open('rb') as stream:
                        assert hashlib.sha1(stream.read()).hexdigest()==sha
                        stream.seek(0)
                        info=tarfile.TarInfo(name)
                        info.size=size
                        info.mode=0o600
                        tar.addfile(info,stream)
        sys.stdout.buffer.flush()
        print(json.dumps(dict(artifact=args.artifact,database=args.database,bytes=sink.size,sha256=sink.hash.hexdigest())),file=sys.stderr)


if __name__=='__main__':
    main()
