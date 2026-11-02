"""Frontend-only follow-up: fresh GPS copy, same dist in Development and Cerro."""
import argparse,fcntl,hashlib,json,os,pwd,subprocess,time
from pathlib import Path
from manage_tracker_user_access import run,sha,query,dump,dist_files,snippet,frontend
from deploy_gps_commissioning import tree,API

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['qa','development','production']);p.add_argument('source',type=Path);p.add_argument('facts',type=Path);a=p.parse_args();assert os.geteuid()==0;os.umask(0o077);source=a.source.resolve()
 commit=subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD'],text=True).strip();assert not subprocess.check_output(['git','-C',str(source),'status','--porcelain','--untracked-files=no'],text=True).strip()
 stage=Path('/opt/steps-validation/tracker-access-ui-20261102')/commit;stage.mkdir(mode=0o700,parents=True,exist_ok=True)
 expected=tree(source/'backend/tracker_py/app');assert expected==tree(API/'app'),'Unexpected API drift'
 with open('/run/lock/steps-environments.lock','a') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX)
  if a.action=='qa':
   assert not (stage/'qa.json').exists();db='TRACKER_ACCESS_GPS_QA_UI_'+str(int(time.time()));backup=stage/'tracker_steps.dump';dump('tracker_steps',backup);run('sudo','-u','postgres','createdb',db)
   facts=json.loads(a.facts.read_text())['cerro'];fp=Path('/tmp/tracker-access-ui-copy-facts.json');fp.write_text(json.dumps({k:facts[k] for k in ('company_id','asset_id')}));fp.chmod(0o600);os.chown(fp,pwd.getpwnam('postgres').pw_uid,pwd.getpwnam('postgres').pw_gid)
   try:
    with backup.open('rb') as f:run('sudo','-u','postgres','pg_restore','--no-owner','--no-acl','-d',db,stdin=f)
    with (stage/'copy.log').open('wb') as log:run('sudo','-u','postgres','env','DATABASE_URL=postgresql+psycopg2:///'+db,'JWT_SECRET=copy-only','TRACKER_ACCESS_FACTS='+str(fp),'PYTHONPATH='+str(source/'backend/tracker_py')+':/opt/steps-validation/personal-transfer-test-deps',API/'.venv/bin/python',source/'tools/qa/tracker/vehicle-access-copy.py',stdout=log,stderr=subprocess.STDOUT)
    (stage/'qa.json').write_text(json.dumps(dict(commit=commit,dist=dist_files(source),api=expected,snippets={k:sha(snippet(k)) for k in ('development','cerro')}),indent=2));print('TRACKER_ACCESS_UI_COPY_QA_OK')
   finally:fp.unlink(missing_ok=True);run('sudo','-u','postgres','dropdb','--if-exists',db)
   return
  proof=json.loads((stage/'qa.json').read_text());assert proof['commit']==commit and proof['dist']==dist_files(source) and proof['api']==expected
  if a.action=='production':assert (stage/'development.json').exists()
  which='development' if a.action=='development' else 'cerro';backup=stage/('backup-'+which+'-'+str(int(time.time())));backup.mkdir(mode=0o700)
  before_receiver=tree(Path('/opt/steps-coban/current').resolve()/'receivers');frontend(source,which,commit,proof,backup)
  assert expected==tree(API/'app') and before_receiver==tree(Path('/opt/steps-coban/current').resolve()/'receivers')
  (stage/(a.action+'.json')).write_text(json.dumps(dict(commit=commit,backup=str(backup),dist=proof['dist'],api_unchanged=True,receiver_unchanged=True)));print('TRACKER_ACCESS_UI_PUBLISHED '+which)
if __name__=='__main__':main()
