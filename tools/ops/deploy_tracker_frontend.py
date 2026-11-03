"""Restore complete Tracker frontend without replacing API, Coban or mobile app."""
import argparse
from datetime import datetime,timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from deploy_gps_commissioning import API,configure_frontend,installed_mobile_root,run,tracker_shell,tree

BASE=Path('/opt/steps-validation/tracker-parity-20261031')


def files(root):return {str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file()}

def entry_package(scope,dist):
 snippet=Path('/etc/nginx/snippets/steps-tracker-'+scope+'-gps.conf')
 content=snippet.read_text()
 mobile=installed_mobile_root(content)
 return {
  'nginx':hashlib.sha256(snippet.read_bytes()).hexdigest(),
  'mobile_release':mobile.name,
  'mobile_assets':files(mobile),
  'shells':{section:hashlib.sha256(tracker_shell((root/'index.html').read_text(encoding='utf-8'),section,scope).encode()).hexdigest()
            for section,root in [('gps',dist),('jornada',mobile)]},
 }


def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['qa','development','production']);p.add_argument('source',type=Path);a=p.parse_args()
 assert os.geteuid()==0;source=a.source.resolve()
 commit=subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD'],text=True).strip()
 assert not subprocess.check_output(['git','-C',str(source),'status','--porcelain','--untracked-files=no'],text=True).strip()
 expected=tree(source/'backend/tracker_py/app');assert expected==tree(API/'app'),'Refuse API drift or frontend package against another API'
 stage=BASE/commit;stage.mkdir(parents=True,exist_ok=True);stage.chmod(0o755)
 private=stage/'private';private.mkdir(exist_ok=True,mode=0o700);private.chmod(0o700)
 assets=files(source/'dist');assert 'index.html' in assets
 with open('/run/lock/steps-environments.lock','a') as lease:
  fcntl.flock(lease,fcntl.LOCK_EX)
  if a.action=='qa':
   assert not (stage/'qa.json').exists()
   entries={scope:entry_package(scope,source/'dist') for scope in ('dev','cerro')}
   run(sys.executable,source/'tools/qa/tracker/test_tracker_entry_routing.py')
   stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ');db='COBAN_QA_'+stamp
   dump=private/'tracker_steps.dump'
   with dump.open('wb') as out:run('sudo','-u','postgres','pg_dump','-Fc','tracker_steps',stdout=out)
   run('pg_restore','--file=/dev/null',dump);run('sudo','-u','postgres','createdb',db)
   try:
    with dump.open('rb') as inp:run('sudo','-u','postgres','pg_restore','--no-owner','--no-acl','-d',db,stdin=inp)
    with (private/'functional.log').open('w') as log:run('sudo','-u','postgres','env','DATABASE_URL=postgresql+psycopg2:///'+db,'JWT_SECRET=test-only-copy-qa','PYTHONPATH='+str(source)+':'+str(source/'backend/tracker_py'),API/'.venv/bin/python',source/'tools/qa/tracker/rehearse_tracker_integration.py',cwd=source,stdout=log,stderr=subprocess.STDOUT)
    assert 'TRACKER_INTEGRATION_COPY_OK' in (private/'functional.log').read_text()
    assert expected==tree(API/'app')
    (stage/'qa.json').write_text(json.dumps({'commit':commit,'api_source':expected,'dist':assets,'entries':entries,'fresh_target_copy':True,'gps_and_classic_session_flow':True,'database':db},indent=2))
    print('TRACKER_FRONTEND_COPY_QA_OK',flush=True)
   finally:run('sudo','-u','postgres','dropdb','--if-exists',db)
   return
  proof=json.loads((stage/'qa.json').read_text());assert proof['commit']==commit and proof['api_source']==expected and proof['dist']==assets
  if a.action=='production':assert json.loads((stage/'development.json').read_text())['dist']==assets
  scope='dev' if a.action=='development' else 'cerro'
  assert proof['entries'][scope]==entry_package(scope,source/'dist'),'Concurrent change to the Tracker entry or mobile assets'
  stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ');backup=private/('backup-'+scope+'-'+stamp);backup.mkdir(mode=0o700)
  untouched={str(root):files(root) for root in [Path('/var/www/web_tracker_portal'),Path('/var/www/steps-truck-frontend'),Path('/opt/steps-coban/current').resolve()]}
  configure_frontend(source,commit,scope,backup)
  assert expected==tree(API/'app')
  for root,original in untouched.items():assert files(Path(root))==original,'Unrelated product changed'
  for service in ('steps-coban','tracker-steps-api','teltonika-ingest','odoo18-cerroelplomo'):run('systemctl','is-active','--quiet',service)
  (stage/(a.action+'.json')).write_text(json.dumps({'commit':commit,'dist':assets,'backup':str(backup),'api_unchanged':True,'receiver_unchanged':True,'legacy_demo_unchanged':True,'mobile_unchanged':True},indent=2))
  print('TRACKER_FRONTEND_PUBLISHED scope='+scope+' commit='+commit,flush=True)


if __name__=='__main__':main()
