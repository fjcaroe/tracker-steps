"""I10 Development only: independent API process, existing masters, private UI alias.

The production API and receiver are never replaced or restarted. One additive
table is shared in tracker_steps; this is process isolation, not a second master.
"""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import shutil
import subprocess
import time
from datetime import datetime, timezone
from urllib.request import urlopen

API = Path('/opt/fernando_odoo18/apis/backend/tracker_py')
PY = API/'.venv/bin/python'
BASE = Path('/opt/steps-validation/mobile-boarding-20261102')
DEV = Path('/opt/steps-tracker-development')
SNIPPET = Path('/etc/nginx/snippets/steps-tracker-dev-gps.conf')
UNIT = Path('/etc/systemd/system/steps-tracker-dev-api.service')
CHANGED = {'models/__init__.py', 'models/passenger_services.py', 'routers/passenger_services.py'}

def run(*cmd, **kw): return subprocess.run(list(map(str, cmd)), check=True, **kw)
def output(*cmd): return subprocess.check_output(list(map(str, cmd)), text=True).strip()
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def tree(root): return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes().replace(b'\r\n', b'\n')).hexdigest() for p in root.rglob('*.py') if '__pycache__' not in p.parts}
def assets(root): return {p.relative_to(root).as_posix(): sha(p) for p in root.rglob('*') if p.is_file()}
def dump(path):
    with path.open('wb') as out: run('sudo','-u','postgres','pg_dump','-Fc','tracker_steps', stdout=out)
    run('pg_restore','--file=/dev/null',path)
def public_verify(front):
    # nginx reload acknowledges before the new worker serves the first request.
    for _ in range(40):
        with urlopen('https://desarrollo.stepsapp.cl/truck/',timeout=30) as response:
            if hashlib.sha256(response.read()).hexdigest()==sha(front/'index.html'): break
        time.sleep(.5)
    else: raise AssertionError('Development did not begin serving the tested index')
    for name, expected in assets(front).items():
        with urlopen('https://desarrollo.stepsapp.cl/truck/'+name, timeout=30) as response:
            assert hashlib.sha256(response.read()).hexdigest() == expected, name
    with urlopen('https://desarrollo.stepsapp.cl/tracker-dev-api/openapi.json') as response:
        assert '/mobile/services/{service_id}/events' in json.load(response)['paths']

def main():
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('action',choices=['qa','development','verify']); parser.add_argument('source',type=Path); a=parser.parse_args()
    assert os.geteuid()==0
    source=a.source.resolve(); commit=output('git','-C',source,'rev-parse','HEAD')
    assert output('git','-C',source,'branch','--show-current')=='codex/steps-movil'
    assert not output('git','-C',source,'status','--porcelain','--untracked-files=no')
    package=tree(source/'backend/tracker_py/app'); production=tree(API/'app')
    assert {k:v for k,v in package.items() if k not in CHANGED} == {k:v for k,v in production.items() if k not in CHANGED}, 'Unreviewed production/API drift'
    front=source/'mobile/dist'; assert 'index.html' in assets(front)
    assert any('/tracker-dev-api' in p.read_text() for p in (front/'assets').glob('*.js')), 'Development API base required'
    stage=BASE/commit; stage.mkdir(parents=True,exist_ok=True); stage.chmod(0o700)
    receiver=tree(Path('/opt/steps-coban/current').resolve()/'receivers')
    untouched={str(p): sha(p) for p in [Path('/etc/nginx/snippets/steps-tracker-cerro-gps.conf'), Path('/var/www/steps-truck-frontend/index.html'), Path('/var/www/web_tracker/index.html')]}
    with open('/run/lock/steps-environments.lock','a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        assert tree(API/'app')==production and tree(Path('/opt/steps-coban/current').resolve()/'receivers')==receiver, 'Runtime changed while waiting for the release lock'
        if a.action=='qa':
            assert not (stage/'qa.json').exists()
            dumpfile=stage/'tracker_steps.dump'; dump(dumpfile)
            db='TRACKER_I10_QA_'+datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')
            run('sudo','-u','postgres','createdb',db)
            try:
                with dumpfile.open('rb') as inp: run('sudo','-u','postgres','pg_restore','--no-owner','--no-acl','-d',db,stdin=inp)
                with (stage/'postgres.log').open('wb') as out:
                    run('sudo','-u','postgres','env','DATABASE_URL=postgresql+psycopg2:///'+db,'JWT_SECRET=private-i10-copy-only','PYTHONPATH='+str(source/'backend/tracker_py'),PY,source/'backend/tracker_py/scripts/rehearse_passenger_events.py',stdout=out,stderr=subprocess.STDOUT)
                assert 'POSTGRES_I10_MIGRATION_OK' in (stage/'postgres.log').read_text()
            finally: run('sudo','-u','postgres','dropdb','--if-exists',db)
            proof=dict(commit=commit,api_package=package,api_production=production,receiver=receiver,untouched=untouched,assets=assets(front),snippet=sha(SNIPPET),fresh_copy=True)
            (stage/'qa.json').write_text(json.dumps(proof,indent=2)); print('I10_QA_OK fresh_copy=True fixtures_rolled_back=True'); return
        proof=json.loads((stage/'qa.json').read_text())
        assert proof['api_package']==package and proof['api_production']==production and proof['receiver']==receiver and proof['assets']==assets(front)
        if a.action=='verify':
            public_verify(front)
            assert tree(API/'app')==production and all(sha(Path(p))==v for p,v in proof['untouched'].items())
            print('I10_DEVELOPMENT_VERIFIED production_api_unchanged=True receiver_unchanged=True cerro_frontend_unchanged=True'); return
        assert proof['snippet']==sha(SNIPPET) and proof['untouched']==untouched, 'Concurrent alias change'
        backup=stage/('backup-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')); backup.mkdir(mode=0o700)
        dump(backup/'tracker_steps.dump'); shutil.copy2(SNIPPET,backup/'nginx.conf')
        existing_api = UNIT.exists() and (DEV/'current').is_symlink()
        if existing_api:
            assert tree(DEV/'current/backend/tracker_py/app')==package, 'Review an API code update separately; this path only reuses identical API code'
            run('systemctl','is-active','--quiet','steps-tracker-dev-api')
            shutil.copy2(UNIT,backup/'existing-api.service')
        else:
            assert not UNIT.exists() and not (DEV/'current').exists(), 'Unexpected partial Development API'
            assert not output('ss','-H','-ltn','sport = :8012'), 'Development port is already occupied'
        # Database changes remain additive and backward compatible on rollback.
        with (source/'backend/tracker_py/migrations/20261102_passenger_events.up.sql').open('rb') as inp:
            run('sudo','-u','postgres','psql','-v','ON_ERROR_STOP=1','-d','tracker_steps',stdin=inp)
        # Reuse the existing native table's grants; never expose credentials.
        grants="""DO $$ DECLARE r record; BEGIN FOR r IN SELECT grantee,privilege_type FROM information_schema.role_table_grants WHERE table_schema='public' AND table_name='mobile_service_passengers' LOOP EXECUTE format('GRANT %s ON TABLE mobile_passenger_events TO %s',r.privilege_type,CASE WHEN r.grantee='PUBLIC' THEN 'PUBLIC' ELSE quote_ident(r.grantee) END); END LOOP; END $$;"""
        run('sudo','-u','postgres','psql','-v','ON_ERROR_STOP=1','-d','tracker_steps','-c',grants)
        if not existing_api:
            target=DEV/'releases'/commit/'backend/tracker_py'; target.mkdir(parents=True)
            shutil.copytree(source/'backend/tracker_py/app',target/'app',ignore=shutil.ignore_patterns('__pycache__'))
            (target/'.env').symlink_to(API/'.env')
            (DEV/'current').symlink_to(target.parents[1])
        unit='''[Unit]
Description=Steps Tracker Development API (I10)
After=network.target postgresql.service
[Service]
Type=simple
User=fernandocaro1198_gmail_com
WorkingDirectory=/opt/steps-tracker-development/current/backend/tracker_py
Environment=PYTHONUNBUFFERED=1
Environment=MOBILE_MEDIA_DIR=/opt/fernando_odoo18/apis/backend/tracker_py/media
ExecStart=/opt/fernando_odoo18/apis/backend/tracker_py/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8012
Restart=on-failure
RestartSec=3
[Install]
WantedBy=multi-user.target
'''
        if not existing_api:
            UNIT.write_text(unit); run('systemctl','daemon-reload')
        else:
            isolated_unit=unit.replace('Environment=PYTHONUNBUFFERED=1','Environment=PYTHONUNBUFFERED=1\nEnvironmentFile=/etc/steps-tracker-development.env')
            assert UNIT.read_text() in (unit,isolated_unit), 'Unexpected Development service configuration'
            if UNIT.read_text()==isolated_unit:
                from urllib.parse import urlsplit
                line=next(x for x in Path('/etc/steps-tracker-development.env').read_text().splitlines() if x.startswith('DATABASE_URL='))
                assert urlsplit(line.partition('=')[2]).path=='/tracker_steps_development', 'Unexpected Development database'
        content=SNIPPET.read_text(); old=set(re.findall(r'/var/www/steps-mobile-releases/[a-f0-9]{40}/',content)); assert len(old)==1
        release=Path('/var/www/steps-mobile-releases')/commit
        if release.exists(): assert assets(release)==assets(front)
        else: shutil.copytree(front,release)
        route='''\n# Dedicated Development process; the hardware receiver still uses the production API.
location ^~ /tracker-dev-api/ {
    proxy_pass http://127.0.0.1:8012/;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_read_timeout 60s;
    add_header Cache-Control "no-store" always;
}
'''
        if existing_api: assert content.count(route)==1, 'Unexpected Development API proxy'
        else: assert '/tracker-dev-api/' not in content
        try:
            if not existing_api: run('systemctl','enable','--now','steps-tracker-dev-api')
            for _ in range(40):
                try:
                    with urlopen('http://127.0.0.1:8012/health',timeout=2) as response:
                        if response.status==200: break
                except OSError: time.sleep(.5)
            else: raise RuntimeError('Development API did not start')
            SNIPPET.write_text(content.replace(next(iter(old)),str(release)+'/')+('' if existing_api else route))
            run('nginx','-t'); run('systemctl','reload','nginx'); public_verify(front)
            assert tree(API/'app')==production and tree(Path('/opt/steps-coban/current').resolve()/'receivers')==receiver
            assert all(sha(Path(p))==value for p,value in untouched.items())
            for service in ('steps-tracker-dev-api','tracker-steps-api','steps-coban','teltonika-ingest','odoo18-dev'): run('systemctl','is-active','--quiet',service)
            (stage/'development.json').write_text(json.dumps(dict(commit=commit,backup=str(backup),port=8012,api_process_isolated=True,database_shared=not Path('/etc/steps-tracker-development.env').exists(),production_api_unchanged=True,receiver_unchanged=True,cerro_frontend_unchanged=True,assets=assets(front)),indent=2))
            print('I10_DEVELOPMENT_PUBLISHED api_port=8012 production_api_unchanged=True cerro_frontend_unchanged=True')
        except Exception:
            shutil.copy2(backup/'nginx.conf',SNIPPET); run('nginx','-t'); run('systemctl','reload','nginx')
            if not existing_api:
                run('systemctl','disable','--now','steps-tracker-dev-api'); UNIT.unlink(); (DEV/'current').unlink(); run('systemctl','daemon-reload')
            raise


if __name__=='__main__': main()
