"""Private disposable I10 HTTP review service, with exact process cleanup."""
import argparse
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import pwd
import signal
import subprocess
import time

def run(*cmd,**kw): return subprocess.run(list(map(str,cmd)),check=True,**kw)
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('action',choices=['start','cleanup']);parser.add_argument('source',type=Path);parser.add_argument('root',type=Path);args=parser.parse_args()
assert os.geteuid()==0
source=args.source.resolve();root=args.root.resolve();assert root.parent==Path('/opt/steps-validation')
meta=root/'review.json'
if args.action=='cleanup':
    state=json.loads(meta.read_text());pid=state['pid'];db=state['db']
    assert db.startswith('TRACKER_I10_UI_QA_') and state['script']==str(source/'tools/qa/tracker/serve_passenger_copy.py')
    proc=Path('/proc')/str(pid)/'cmdline'
    if proc.exists():
        assert state['script'] in proc.read_bytes().replace(b'\0',b' ').decode()
        assert os.getpgid(pid)==pid
        os.killpg(pid,signal.SIGTERM)
        for _ in range(30):
            if not proc.exists(): break
            time.sleep(.2)
    run('sudo','-u','postgres','dropdb','--if-exists',db)
    (root/'qa/proof.json').unlink(missing_ok=True);meta.unlink();print('I10_REVIEW_CLEANED private_database_removed=True token_file_removed=True')
else:
    assert not meta.exists()
    assert not subprocess.check_output(['ss','-H','-ltn','sport = :18012']).strip()
    root.mkdir(mode=0o755,parents=True,exist_ok=True);output=root/'qa';output.mkdir(mode=0o700)
    postgres=pwd.getpwnam('postgres');os.chown(output,postgres.pw_uid,postgres.pw_gid)
    db='TRACKER_I10_UI_QA_'+datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')
    dump=root/'source.dump'
    with dump.open('wb') as out:run('sudo','-u','postgres','pg_dump','-Fc','tracker_steps',stdout=out)
    dump.chmod(0o600);run('pg_restore','--file=/dev/null',dump)
    run('sudo','-u','postgres','createdb',db)
    try:
        with dump.open('rb') as inp:run('sudo','-u','postgres','pg_restore','--no-owner','--no-acl','-d',db,stdin=inp)
        with (source/'backend/tracker_py/migrations/20261102_passenger_events.up.sql').open('rb') as inp:run('sudo','-u','postgres','psql','-v','ON_ERROR_STOP=1','-d',db,stdin=inp,stdout=subprocess.DEVNULL)
        run('sudo','-u','postgres','psql','-d','postgres','-c','REVOKE CONNECT ON DATABASE "'+db+'" FROM PUBLIC;',stdout=subprocess.DEVNULL)
        script=source/'tools/qa/tracker/serve_passenger_copy.py'
        env=['DATABASE_URL=postgresql+psycopg2:///'+db,'JWT_SECRET=private-i10-browser-copy-only','PYTHONPATH='+str(source/'backend/tracker_py'),'PASSENGER_UI_PROOF='+str(output/'proof.json')]
        with (root/'server.log').open('wb') as log:
            process=subprocess.Popen(['sudo','-u','postgres','env',*env,'/opt/fernando_odoo18/apis/backend/tracker_py/.venv/bin/python',str(script)],start_new_session=True,stdout=log,stderr=subprocess.STDOUT,cwd=source)
        meta.write_text(json.dumps(dict(pid=process.pid,db=db,script=str(script))));meta.chmod(0o600)
        for _ in range(100):
            if (output/'proof.json').exists() and b'PASSENGER_COPY_SERVER_READY' in (root/'server.log').read_bytes():break
            if process.poll() is not None:raise RuntimeError('Read private review server log')
            time.sleep(.2)
        else:raise RuntimeError('Review server startup timed out')
        print('I10_REVIEW_SERVER_READY port=18012 private_copy=True')
    except Exception:
        if not meta.exists():run('sudo','-u','postgres','dropdb','--if-exists',db)
        raise
