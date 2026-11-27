"""Capture complete PostgreSQL constraints for semantic comparison after a logical restore."""
import gzip
import hashlib
import json
import sys

import psycopg2

from audit_cerro_original_schema import catalogue,queries


def detail(db,host='/var/run/postgresql',port=5432):
    with psycopg2.connect(dbname=db,host=host,port=port,user='postgres') as conn,conn.cursor() as cr:
        conn.set_session(readonly=True,isolation_level='REPEATABLE READ')
        cr.execute('SET LOCAL search_path=pg_catalog,public')
        names,rows=catalogue(cr,queries()['constraints'])
        section=hashlib.sha256(json.dumps(sorted(rows.items()),separators=(',',':')).encode()).hexdigest()
        cr.execute("""SELECT ARRAY[n.nspname,c.relname,k.conname],pg_get_constraintdef(k.oid,false)
            FROM pg_constraint k JOIN pg_class c ON c.oid=k.conrelid JOIN pg_namespace n ON n.oid=c.relnamespace
            WHERE n.nspname !~ '^pg_' AND n.nspname<>'information_schema'""")
        definitions={tuple(key):value for key,value in cr}
        return {'columns':names,'sha256':section,'rows':[[key,value,definitions[key]] for key,value in sorted(rows.items())]}


def verify_deparse(source,db,socket,port,source_digest,restored_digest):
    from cerro_accounting_checks import CHECKS,ELEM,ARRAY
    local=detail(db,str(socket),port)
    assert source['sha256']==source_digest and local['sha256']==restored_digest
    names=source['columns']
    assert names==local['columns']
    raw={tuple(k):(row,definition) for k,row,definition in source['rows']}
    recovered={tuple(k):(row,definition) for k,row,definition in local['rows']}
    assert raw.keys()==recovered.keys()
    changes=[]
    for key in raw.keys():
        old,original=raw[key]
        new,restored=recovered[key]
        if (old,original)==(new,restored):
            continue
        assert key[:2]==('public','account_move_line') and key[2] in CHECKS
        assert [name for name,a,b in zip(names,old,new) if a!=b]==['definition_md5']
        assert hashlib.md5(original.encode()).hexdigest()==old[names.index('definition_md5')]
        assert hashlib.md5(restored.encode()).hexdigest()==new[names.index('definition_md5')]
        assert original.count(ARRAY)==restored.count(ELEM)==1
        assert original.replace(ARRAY,'LIST')==restored.replace(ELEM,'LIST')
        changes.append(key[2])
    assert set(changes)==set(CHECKS)
    with psycopg2.connect(dbname=db,host=str(socket),port=port,user='postgres') as conn,conn.cursor() as cr:
        cr.execute('SELECT ('+ELEM+') IS NOT DISTINCT FROM ('+ARRAY+')')
        assert cr.fetchone()==(True,)
    return sorted(changes)


if __name__=='__main__':
    from backup_cerro_catalog_pilots import PILOTS
    from fcntl import flock,LOCK_SH
    assert sys.argv[1] in PILOTS
    with open('/run/lock/steps-environments.lock','rb') as lock:
        flock(lock,LOCK_SH)
        data=gzip.compress(json.dumps(detail(sys.argv[1]),separators=(',',':')).encode(),compresslevel=5,mtime=0)
        sys.stdout.buffer.write(data)
        print(hashlib.sha256(data).hexdigest(),file=sys.stderr)
