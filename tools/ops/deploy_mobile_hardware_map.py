"""Cerro-scoped mobile GPS publication; API, hardware receiver and shared app stay intact."""
import argparse
from datetime import datetime,timezone
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
from urllib.request import urlopen

BASE=Path('/opt/steps-validation/mobile-hardware-map-20261031')
API=Path('/opt/fernando_odoo18/apis/backend/tracker_py')
SNIPPETS={'development':Path('/etc/nginx/snippets/steps-tracker-dev-gps.conf'),'production':Path('/etc/nginx/snippets/steps-tracker-cerro-gps.conf')}
HOSTS={'development':'desarrollo.stepsapp.cl','production':'cerroelplomo.stepsapp.cl'}


def run(*args,**kw):return subprocess.run([str(a) for a in args],check=True,**kw)
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def files(root):return {str(p.relative_to(root)):digest(p) for p in root.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
def python_tree(root):return {str(p.relative_to(root)):hashlib.sha256(p.read_bytes().replace(b'\r\n',b'\n')).hexdigest() for p in root.rglob('*.py') if '__pycache__' not in p.parts}


def verify(source,host):
 for _ in range(20):
  with urlopen('https://'+host+'/truck/',timeout=20) as r:equal=r.read()==(source/'mobile/dist/index.html').read_bytes()
  if equal:break
  time.sleep(.5)
 assert equal,'Served app does not match tested index'
 for path in (source/'mobile/dist').rglob('*'):
  if path.is_file():
   with urlopen('https://'+host+'/truck/'+path.relative_to(source/'mobile/dist').as_posix(),timeout=20) as response:assert hashlib.sha256(response.read()).hexdigest()==digest(path)


def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['qa','development','production','verify']);p.add_argument('source',type=Path);a=p.parse_args()
 assert os.geteuid()==0
 source=a.source.resolve();commit=subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD'],text=True).strip()
 assert subprocess.check_output(['git','-C',str(source),'branch','--show-current'],text=True).strip()=='codex/steps-movil'
 assert not subprocess.check_output(['git','-C',str(source),'status','--porcelain','--untracked-files=no'],text=True).strip()
 expected=python_tree(source/'backend/tracker_py/app');assert expected==python_tree(API/'app'),'Refuse backend drift or downgrade'
 assets=files(source/'mobile/dist');assert 'index.html' in assets
 stage=BASE/commit;stage.mkdir(parents=True,exist_ok=True);stage.chmod(0o755)
 receiver=Path('/opt/steps-coban/current').resolve();receiver_hash=python_tree(receiver/'receivers')
 with open('/run/lock/steps-environments.lock','a') as lease:
  fcntl.flock(lease,fcntl.LOCK_EX)
  if a.action=='qa':
   assert not (stage/'qa.json').exists()
   private=stage/'private';private.mkdir(mode=0o700)
   output=stage/'qa-data';output.mkdir(mode=0o700);postgres=pwd.getpwnam('postgres');os.chown(output,postgres.pw_uid,postgres.pw_gid)
   dump=private/'tracker_steps.dump'
   with dump.open('wb') as out:run('sudo','-u','postgres','pg_dump','-Fc','tracker_steps',stdout=out)
   run('pg_restore','--file=/dev/null',dump)
   db='COBAN_QA_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ');run('sudo','-u','postgres','createdb',db)
   try:
    with dump.open('rb') as inp:run('sudo','-u','postgres','pg_restore','--no-owner','--no-acl','-d',db,stdin=inp)
    with (private/'functional.log').open('w') as log:run('sudo','-u','postgres','env','DATABASE_URL=postgresql+psycopg2:///'+db,'JWT_SECRET=test-only-hardware-qa','PYTHONPATH='+str(source/'backend/tracker_py')+':'+str(receiver),API/'.venv/bin/python',source/'tools/qa/tracker/rehearse_mobile_hardware.py',output/'snapshot.json',cwd=source,stdout=log,stderr=subprocess.STDOUT)
    assert 'MOBILE_HARDWARE_COPY_OK' in (private/'functional.log').read_text()
    proof={'commit':commit,'assets':assets,'api':expected,'receiver':receiver_hash,'snippets':{k:digest(v) for k,v in SNIPPETS.items()},'fresh_target_copy':True,'tcp_to_mobile_snapshot':True,'no_journey_required':True}
    assert expected==python_tree(API/'app') and receiver_hash==python_tree(receiver/'receivers')
    (stage/'qa.json').write_text(json.dumps(proof,indent=2));print('MOBILE_HARDWARE_QA_OK',flush=True)
   finally:run('sudo','-u','postgres','dropdb','--if-exists',db)
   return
  proof=json.loads((stage/'qa.json').read_text());assert proof['assets']==assets and proof['api']==expected and proof['receiver']==receiver_hash
  if a.action=='verify':
   for host in HOSTS.values():verify(source,host)
   print('MOBILE_HARDWARE_LIVE_OK source_exact=True api_unchanged=True receiver_unchanged=True');return
  if a.action=='production':assert json.loads((stage/'development.json').read_text())['commit']==commit
  snippet=SNIPPETS[a.action];assert digest(snippet)==proof['snippets'][a.action],'Concurrent nginx change'
  content=snippet.read_text();assert content.count('/var/www/steps-truck-frontend/')==2,'Review a changed mobile alias explicitly'
  backup=stage/'private'/('backup-'+a.action+'-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'));backup.mkdir(mode=0o700);shutil.copy2(snippet,backup/snippet.name)
  untouched={str(root):files(root) for root in [Path('/var/www/steps-truck-frontend'),Path('/var/www/web_tracker_portal'),Path('/var/www/web_tracker')]}
  target=Path('/var/www/steps-mobile-releases')/commit
  if target.exists():assert files(target)==assets
  else:shutil.copytree(source/'mobile/dist',target)
  snippet.write_text(content.replace('/var/www/steps-truck-frontend/',str(target)+'/'))
  try:
   run('nginx','-t');run('systemctl','reload','nginx');verify(source,HOSTS[a.action])
   assert expected==python_tree(API/'app') and receiver_hash==python_tree(receiver/'receivers')
   for root,before in untouched.items():assert before==files(Path(root))
   for service in ('tracker-steps-api','steps-coban','teltonika-ingest'):run('systemctl','is-active','--quiet',service)
   (stage/(a.action+'.json')).write_text(json.dumps({'commit':commit,'backup':str(backup),'assets':assets,'api_unchanged':True,'receiver_unchanged':True,'shared_frontends_unchanged':True},indent=2))
   print('MOBILE_HARDWARE_PUBLISHED scope='+a.action+' commit='+commit,flush=True)
  except Exception:shutil.copy2(backup/snippet.name,snippet);run('nginx','-t');run('systemctl','reload','nginx');raise


if __name__=='__main__':main()
