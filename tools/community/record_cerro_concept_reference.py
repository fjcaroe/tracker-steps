"""Record a native user exercise on the dedicated original Cerro QA copy; return consumed sequences."""
import fcntl
import json
from pathlib import Path
import subprocess
import sys

import psycopg2
from psycopg2 import sql

from check_cerro_schema_counterexamples import native_read
from restore_cerro_native_catalog_graph import TARGET as NATIVE

DEST=Path('/opt/steps-validation/community-cerro-concepts-20261127U45P')
P='COMMUNITY_CERRO_BOM_CONCEPTS_20261127U45P'
BODY="import json,sys\nsys.path.insert(0,"+repr(str(DEST/'code'))+")\nfrom probe_cerro_payment_concepts import exercise\nprint('PAYMENT_USER',json.dumps(exercise(env),sort_keys=True))"


def sequences(db,restore=None):
    assert db in (NATIVE,P)
    with psycopg2.connect(dbname=db) as conn,conn.cursor() as cr:
        cr.execute("SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() AND pid<>pg_backend_pid()")
        assert cr.fetchone()==(0,)
        cr.execute("SELECT schemaname,sequencename FROM pg_sequences WHERE schemaname='public' ORDER BY 1,2")
        names=cr.fetchall()
        current={}
        for schema,name in names:
            cr.execute(sql.SQL('SELECT last_value,is_called FROM {}').format(sql.Identifier(schema,name)))
            current[name]=list(cr.fetchone())
        if restore is None:
            return current
        assert current.keys()==restore.keys()
        changed=[]
        for name,before in restore.items():
            if current[name]!=before:
                cr.execute('SELECT setval(to_regclass(%s),%s,%s)',('public.'+name,*before))
                changed.append(name)
        return changed


def state(db,before=None):
    mode='snapshot' if before is None else 'restore'
    env='PYTHONPATH='+str(DEST/'code')+':/opt/steps-validation/community-cerro-studio-strict-20261126U42C/tools'
    result=subprocess.check_output(['runuser','-u','postgres','--','env',env,'/usr/bin/python3.10',str(Path(__file__).resolve()),mode,db],
                                 input=None if before is None else json.dumps(before).encode())
    return json.loads(result)


def reference():
    before=state(NATIVE)
    try:
        user=native_read(BODY,'payment-concepts','PAYMENT_USER')
    finally:
        restored=state(NATIVE,before)
        assert state(NATIVE)==before
    result=dict(user=user,sequences_restored=restored)
    (DEST/'native-concept-user.json').write_text(json.dumps(result,sort_keys=True))
    return user


if __name__=='__main__':
    if sys.argv[1:]:
        mode,database=sys.argv[1:]
        assert mode in ('snapshot','restore')
        print(json.dumps(sequences(database,None if mode=='snapshot' else json.load(sys.stdin)),sort_keys=True))
    else:
        with open('/run/lock/steps-environments.lock','rb') as gate:
            fcntl.flock(gate,fcntl.LOCK_EX)
            reference()
