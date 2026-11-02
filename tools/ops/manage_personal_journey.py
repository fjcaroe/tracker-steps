"""QA and apply explicitly selected Development fixture cleanup plus real onboarding."""
import argparse,configparser,fcntl,hashlib,json,os,pwd,shutil,subprocess,time
from datetime import datetime,timezone
from pathlib import Path
API=Path('/opt/fernando_odoo18/apis/backend/tracker_py');PY=API/'.venv/bin/python'
def run(*cmd,**kw):return subprocess.run(list(map(str,cmd)),check=True,**kw)
def out(*cmd,**kw):return subprocess.check_output(list(map(str,cmd)),text=True,**kw).strip()
def dump(db,path):
 with path.open('wb') as f:run('sudo','-u','postgres','pg_dump','-Fc',db,stdout=f)
 run('pg_restore','--file=/dev/null',path)
def clone(db,path,owner=None):
 run('sudo','-u','postgres','createdb',*(['-O',owner] if owner else []),db)
 with path.open('rb') as f:run('sudo','-u','postgres','pg_restore','--no-owner','--no-acl',*(['--role',owner] if owner else []),'-d',db,stdin=f)
def worker(source,db,plan):
 return json.loads(out('sudo','-u','postgres',PY,source/'tools/gps/prepare_personal_journey_data.py',db,plan))
def native(source,db,plan,ids,stage):
 prefix='/tmp/journey-'+str(time.time_ns());user=pwd.getpwnam('odoo');paths=[]
 try:
  for suffix,value in [('plan',json.loads(plan.read_text())),('ids',ids)]:
   p=Path(prefix+'-'+suffix+'.json');p.write_text(json.dumps(value));p.chmod(0o600);os.chown(p,user.pw_uid,user.pw_gid);paths.append(p)
  with (source/'tools/gps/prepare_personal_journey_native.py').open('rb') as inp,(stage/(db+'-native.log')).open('wb') as log:
   run('sudo','-u','odoo','env','JOURNEY_PLAN='+str(paths[0]),'JOURNEY_IDS='+str(paths[1]),'PYTHONPATH=/opt/odoo18','/usr/bin/python3.10','/opt/odoo18/odoo-bin','shell','-c','/etc/dev_odoo18.conf','-d',db,'--db-filter=^'+db+'$','--no-http','--workers=0','--max-cron-threads=0','--logfile=/tmp/'+db+'-journey.log',stdin=inp,stdout=log,stderr=subprocess.STDOUT)
  assert 'PERSONAL_JOURNEY_NATIVE_READY' in (stage/(db+'-native.log')).read_text()
 finally:
  for p in paths:p.unlink(missing_ok=True)
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['qa','apply']);p.add_argument('source',type=Path);p.add_argument('plan',type=Path);p.add_argument('root',type=Path);p.add_argument('--keep-review',action='store_true');a=p.parse_args()
 assert os.geteuid()==0;os.umask(0o077);source=a.source.resolve();root=a.root;root.mkdir(parents=True,exist_ok=True);root.chmod(0o700)
 assert not out('git','-C',source,'status','--porcelain','--untracked-files=no');commit=out('git','-C',source,'rev-parse','HEAD')
 plan=json.loads(a.plan.read_text());assert plan['passenger_capacity']==4 and plan['company_id']==1 and plan['user_id']==6
 stage=root/commit;stage.mkdir(exist_ok=True);proof_file=stage/'qa.json'
 with open('/run/lock/steps-environments.lock','a') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX)
  if a.action=='qa':
   assert not proof_file.exists()
   for db in ('tracker_steps','LAB_TAREAS'):dump(db,stage/(db+'.dump'))
   stamp=datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S');gps='PERSONAL_JOURNEY_QA_'+stamp;odoo='PERSONAL_JOURNEY_NATIVE_QA_'+stamp
   cfg=configparser.ConfigParser(interpolation=None);cfg.read('/etc/dev_odoo18.conf');clones=[]
   try:
    clone(gps,stage/'tracker_steps.dump');clones.append(gps)
    qa_plan=Path('/tmp/journey-plan-'+stamp+'.json');qa_plan.write_bytes(a.plan.read_bytes());qa_plan.chmod(0o600);postgres=pwd.getpwnam('postgres');os.chown(qa_plan,postgres.pw_uid,postgres.pw_gid)
    try:ids=worker(source,gps,qa_plan)
    finally:qa_plan.unlink()
    (stage/'qa-ids.json').write_text(json.dumps(ids,indent=2))
    clone(odoo,stage/'LAB_TAREAS.dump',cfg['options']['db_user']);clones.append(odoo)
    run('sudo','-u','postgres','psql','-d',odoo,'-c','UPDATE ir_cron SET active=false;UPDATE ir_mail_server SET active=false;',stdout=subprocess.DEVNULL)
    native(source,odoo,a.plan,ids,stage)
    with (stage/'functional.log').open('wb') as log:
     run('sudo','-u','postgres','env','DATABASE_URL=postgresql+psycopg2:///'+gps,'JWT_SECRET=private-journey-copy-only','JOURNEY_QA_IDS='+json.dumps(ids),'PYTHONPATH='+str(source/'backend/tracker_py')+':/opt/steps-validation/personal-transfer-test-deps',PY,source/'tools/qa/tracker/rehearse_personal_journey.py',stdout=log,stderr=subprocess.STDOUT)
    assert 'PERSONAL_JOURNEY_API_OK' in (stage/'functional.log').read_text()
    proof_file.write_text(json.dumps(dict(commit=commit,plan_sha=hashlib.sha256(a.plan.read_bytes()).hexdigest(),ids=ids,native=True,api=True,review_db=gps if a.keep_review else None),indent=2));print('PERSONAL_JOURNEY_QA_OK',flush=True)
   finally:
    for db in reversed(clones):
     if db==gps and a.keep_review and proof_file.exists():continue
     run('sudo','-u','postgres','dropdb','--if-exists',db)
   return
  proof=json.loads(proof_file.read_text());assert proof['commit']==commit and proof['plan_sha']==hashlib.sha256(a.plan.read_bytes()).hexdigest() and proof['native'] and proof['api']
  backup=stage/('backup-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'));backup.mkdir(mode=0o700)
  for db in ('tracker_steps','LAB_TAREAS'):dump(db,backup/(db+'.dump'))
  private=Path('/tmp/journey-live-plan-'+str(time.time_ns())+'.json');private.write_bytes(a.plan.read_bytes());private.chmod(0o600);postgres=pwd.getpwnam('postgres');os.chown(private,postgres.pw_uid,postgres.pw_gid)
  try:ids=worker(source,'tracker_steps',private)
  finally:private.unlink()
  (stage/'live-ids.json').write_text(json.dumps(ids,indent=2))
  native(source,'LAB_TAREAS',a.plan,ids,stage)
  (stage/'delivery.json').write_text(json.dumps(dict(commit=commit,ids=ids,backup=str(backup),native=True,api=True),indent=2));print('PERSONAL_JOURNEY_APPLIED archived_native='+str(len(plan['retire_vehicle_ids']))+' unused_assets_removed='+str(ids['retired_assets']),flush=True)
if __name__=='__main__':main()
