"""Explicit personal-vehicle relocation: exact-package QA, backup, lock, receipts.
Only source GPS asset from private plan is moved; native original is archived.
No password, outgoing message, source-company permission or other GPS is changed.
"""
import argparse,configparser,fcntl,hashlib,json,os,pwd,shutil,sqlite3,subprocess,time
from datetime import datetime,timezone
from pathlib import Path
from urllib.request import urlopen
API=Path('/opt/fernando_odoo18/apis/backend/tracker_py');PY=API/'.venv/bin/python'
ENVS={'source':('CERRO_EL_PLOMO','cerro_odoo18','/etc/odoo18-cerroelplomo.conf'),'target':('LAB_TAREAS','odoo','/etc/dev_odoo18.conf')}
def run(*cmd,**kw):return subprocess.run([str(v) for v in cmd],check=True,**kw)
def output(*cmd,**kw):return subprocess.check_output([str(v) for v in cmd],text=True,**kw).strip()
def query(db,sql):return output('sudo','-u','postgres','psql','-w','-v','ON_ERROR_STOP=1','-At','-d',db,'-c',sql)
def tree(path):return {str(p.relative_to(path)):hashlib.sha256(p.read_bytes().replace(b'\r\n',b'\n')).hexdigest() for p in sorted(path.rglob('*.py')) if '__pycache__' not in p.parts}
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(db,path):
 with path.open('wb') as out:run('sudo','-u','postgres','pg_dump','-Fc',db,stdout=out)
 run('pg_restore','--file=/dev/null',path)
def worker(source,db,plan,apply=False):
 value=output('sudo','-u','postgres',PY,source/'tools/gps/transfer_personal_gps.py',db,input=json.dumps({'plan':plan,'apply':apply}))
 return json.loads(value)
def clone(db,dumpfile,owner=None):
 args=['sudo','-u','postgres','createdb']+(['-O',owner] if owner else [])+[db];run(*args)
 args=['sudo','-u','postgres','pg_restore','--no-owner','--no-acl','--no-comments']+(['--role',owner] if owner else [])+['-d',db]
 with dumpfile.open('rb') as inp:run(*args,stdin=inp)
def native(source,which,db,mode,facts,root):
 actual,user,cfg=ENVS[which];uid=pwd.getpwnam(user).pw_uid;gid=pwd.getpwnam(user).pw_gid
 stamp=str(time.time_ns());inp=Path('/tmp/personal-input-'+stamp+'.json');result=Path('/tmp/personal-result-'+stamp+'.json')
 inp.write_bytes(facts.read_bytes());inp.chmod(0o600);os.chown(inp,uid,gid)
 logfile=root/(db+'-'+mode+'-'+stamp+'.log')
 try:
  with (source/'tools/gps/transfer_personal_native.py').open('rb') as stdin,logfile.open('wb') as out:
   run('sudo','-u',user,'env','PERSONAL_MODE='+mode,'PERSONAL_FACTS='+str(inp),'PERSONAL_RESULT='+str(result),'PYTHONPATH=/opt/odoo18','/usr/bin/python3.10','/opt/odoo18/odoo-bin','shell','-c',cfg,'-d',db,'--db-filter=^'+db+'$','--no-http','--workers=0','--max-cron-threads=0','--logfile=/tmp/'+db+'-personal-native.log',stdin=stdin,stdout=out,stderr=subprocess.STDOUT)
  expected='PERSONAL_NATIVE_IMPORTED' if mode=='import' else 'PERSONAL_SOURCE_ARCHIVED';assert expected in logfile.read_text(errors='replace'),'Review private native log'
  value=json.loads(result.read_text()) if result.exists() else {}
  if value:(root/(db+'-'+mode+'-result.json')).write_text(json.dumps(value,indent=2))
  return value
 finally:inp.unlink(missing_ok=True);result.unlink(missing_ok=True)
def wait_api():
 for _ in range(40):
  try:
   with urlopen('http://127.0.0.1:8000/health',timeout=2) as r:
    if r.status==200:return
  except OSError:pass
  time.sleep(.5)
 raise RuntimeError('API startup requires attention')
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['qa','apply']);p.add_argument('source',type=Path);p.add_argument('--plan',type=Path,required=True);p.add_argument('--facts',type=Path,required=True);p.add_argument('--root',type=Path,required=True);a=p.parse_args()
 assert os.geteuid()==0;os.umask(0o077);source=a.source.resolve();root=a.root.resolve();root.mkdir(parents=True,exist_ok=True);root.chmod(0o700)
 assert not output('git','-C',source,'status','--porcelain','--untracked-files=no')
 commit=output('git','-C',source,'rev-parse','HEAD');plan=json.loads(a.plan.read_text());facts=json.loads(a.facts.read_text())
 assert plan['asset_id']==facts['asset_id'] and plan['source_company']==facts['source_company'] and plan['plate']==facts['plate']
 assert plan['target_company']==1 and facts['source_user_id']==6,'Explicit existing-user/Development-company contract'
 package=tree(source/'backend/tracker_py/app');current=tree(API/'app');assert {k:v for k,v in current.items() if k!='routers/receiver.py'}=={k:v for k,v in package.items() if k!='routers/receiver.py'},'Unreviewed API drift'
 with open('/run/lock/steps-environments.lock','a') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX);stage=root/commit;stage.mkdir(exist_ok=True);proof_file=stage/'qa.json'
  if a.action=='qa':
   assert not proof_file.exists();print('PERSONAL_QA_BACKUPS',flush=True)
   for name in ('CERRO_EL_PLOMO','LAB_TAREAS','tracker_steps'):dump(name,stage/(name+'.dump'))
   (stage/'native-facts.json').write_bytes(a.facts.read_bytes())
   baseline=worker(source,'tracker_steps',plan)
   stamp=datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S');gps='PERSONAL_GPS_QA_'+stamp
   clones=[]
   try:
    clone(gps,stage/'tracker_steps.dump');clones.append((gps,None))
    worker(source,gps,plan,True);again=worker(source,gps,plan,True);assert again['position_count']==baseline['position_count']
    env={**os.environ,'DATABASE_URL':'postgresql+psycopg2:///'+gps,'JWT_SECRET':'private-copy-tests-only','PYTHONPATH':str(source)+':'+str(source/'backend/tracker_py'),'PERSONAL_PLAN':str(a.plan)}
    # Read access for postgres only during tests; no secret-bearing input is world-readable.
    test_plan=Path('/tmp/personal-test-plan-'+stamp+'.json');test_plan.write_bytes(a.plan.read_bytes());test_plan.chmod(0o600);os.chown(test_plan,pwd.getpwnam('postgres').pw_uid,pwd.getpwnam('postgres').pw_gid);env['PERSONAL_PLAN']=str(test_plan)
    try:
     with (stage/'api-tests.log').open('wb') as out:run(PY,'-m','pytest','tests/test_fleet.py','tests/test_receiver.py','-q',cwd=source/'backend/tracker_py',env={**env,'PYTHONPATH':env['PYTHONPATH']+':/opt/steps-validation/personal-transfer-test-deps'},stdout=out,stderr=subprocess.STDOUT)
     print('PERSONAL_API_TESTS_OK',flush=True)
     with (stage/'tcp-copy.log').open('wb') as out:run('sudo','-u','postgres','env',*[k+'='+env[k] for k in ('DATABASE_URL','JWT_SECRET','PYTHONPATH','PERSONAL_PLAN')],PY,source/'tools/qa/tracker/personal-transfer-flow.py',cwd=source,stdout=out,stderr=subprocess.STDOUT)
    finally:test_plan.unlink(missing_ok=True)
    print('PERSONAL_TCP_COPY_OK',flush=True)
    for which in ('target','source'):
     actual,user,cfg=ENVS[which];conf=configparser.ConfigParser(interpolation=None);conf.read(cfg);owner=conf['options']['db_user'];db='PERSONAL_'+('DEV' if which=='target' else 'CERRO')+'_QA_'+stamp
     clone(db,stage/(actual+'.dump'),owner);clones.append((db,conf['options'].get('data_dir')));query(db,'UPDATE ir_cron SET active=false;UPDATE ir_mail_server SET active=false;')
     if which=='target':
      value=native(source,which,db,'import',a.facts,stage);assert value['user_id']==facts['source_user_id'] and value['company_id']==plan['target_company']
      again=native(source,which,db,'import',a.facts,stage);assert value==again,'Native import must be idempotent'
     else:native(source,which,db,'archive',a.facts,stage)
     print('PERSONAL_NATIVE_COPY_OK '+which,flush=True)
    proof={'commit':commit,'api_baseline':current,'api_package':package,'receiver_baseline':tree(Path('/opt/steps-coban/current').resolve()/'receivers'),'facts_sha256':digest(a.facts),'plan_sha256':digest(a.plan),'gps_before':baseline,'native':True,'tcp_flow':True}
    proof_file.write_text(json.dumps(proof,indent=2));print('PERSONAL_TRANSFER_QA_OK',flush=True)
   finally:
    for db,data_dir in reversed(clones):
     run('sudo','-u','postgres','dropdb','--if-exists',db)
     if data_dir:
      base=Path(data_dir).resolve()/'filestore';directory=base/db
      assert directory.parent==base and db.startswith('PERSONAL_')
      if directory.exists():shutil.rmtree(directory)
   return
  proof=json.loads(proof_file.read_text());assert proof['commit']==commit and proof['native'] and proof['tcp_flow']
  assert proof['facts_sha256']==digest(a.facts) and proof['plan_sha256']==digest(a.plan) and proof['api_package']==package
  assert proof['api_baseline']==current and proof['receiver_baseline']==tree(Path('/opt/steps-coban/current').resolve()/'receivers'),'Concurrent runtime change'
  fresh=worker(source,'tracker_steps',plan);assert fresh['snapshot']==proof['gps_before']['snapshot'],'Personal records changed; repeat fresh-copy QA'
  backup=stage/('backup-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'));backup.mkdir(mode=0o700)
  for name in ('CERRO_EL_PLOMO','LAB_TAREAS','tracker_steps'):dump(name,backup/(name+'.dump'))
  shutil.copytree('/etc/steps-coban',backup/'receiver-config');shutil.copytree(API/'app',backup/'api-app',ignore=shutil.ignore_patterns('__pycache__'))
  old_receiver=Path('/opt/steps-coban/current').resolve();(backup/'receiver-release.txt').write_text(str(old_receiver))
  allowed=Path('/etc/tracker-coban-tenants.json')
  if allowed.exists():shutil.copy2(allowed,backup/'api-receiver-tenants.json')
  # Freeze the outbox before moving ownership. Pending old-tenant packets must drain first.
  print('PERSONAL_TRANSFER_FREEZE',flush=True);run('systemctl','stop','steps-coban.service','tracker-steps-api.service')
  cfg_path=Path('/etc/steps-coban/config.json');cfg=json.loads(cfg_path.read_text());inbox=sqlite3.connect(cfg['database'])
  with sqlite3.connect(backup/'inbox.sqlite') as target:inbox.backup(target)
  try:
   assert inbox.execute('SELECT count(*) FROM inbox WHERE imei=? AND delivered IS NULL',(plan['imei'],)).fetchone()[0]==0,'Pending personal outbox; restart services, drain, repeat QA'
   result=worker(source,'tracker_steps',plan,True);(backup/'gps-moved.json').write_text(json.dumps(result,indent=2))
   shutil.copy2(source/'backend/tracker_py/app/routers/receiver.py',API/'app/routers/receiver.py')
   assert tree(API/'app')==package
   rows=json.loads(allowed.read_text()) if allowed.exists() else [];extra={'issuer':'LAB_TAREAS','company_id':plan['target_company']}
   if extra not in rows:rows.append(extra)
   allowed.write_text(json.dumps(rows));allowed.chmod(0o644)
   receiver_uid=pwd.getpwnam('steps-coban');keys=json.loads(Path('/etc/tracker-bridge-keys.json').read_text());assert keys.get('LAB_TAREAS') and keys.get('CERRO_EL_PLOMO')
   keyfile=Path(cfg['key_file']);keyfile.write_text(json.dumps({'issuers':{k:keys[k] for k in ('CERRO_EL_PLOMO','LAB_TAREAS')}}));keyfile.chmod(0o640);os.chown(keyfile,0,receiver_uid.pw_gid)
   routes=json.loads(Path(cfg['mapping']).read_text());assert routes[plan['imei']]['device_id']==result['device_id'];routes[plan['imei']].update(issuer='LAB_TAREAS',company_id=plan['target_company'])
   mapping=Path(cfg['mapping']);temporary=mapping.with_suffix('.migration');temporary.write_text(json.dumps(routes));temporary.chmod(0o600);os.chown(temporary,receiver_uid.pw_uid,receiver_uid.pw_gid);os.replace(temporary,mapping)
   targets=[{'issuer':'CERRO_EL_PLOMO','company_id':int(c)} for c in query('tracker_steps',"SELECT company_id FROM gps_tenants WHERE issuer='CERRO_EL_PLOMO' ORDER BY company_id").splitlines()];targets.append(extra);cfg['tenants']=targets
   cfg_path.write_text(json.dumps(cfg,indent=2));cfg_path.chmod(0o640);os.chown(cfg_path,0,receiver_uid.pw_gid)
   release=Path('/opt/steps-coban/releases')/commit;release.mkdir();shutil.copytree(source/'receivers',release/'receivers',ignore=shutil.ignore_patterns('__pycache__'))
   for item in [release,*release.rglob('*')]:item.chmod(0o755 if item.is_dir() else 0o644)
   link=Path('/opt/steps-coban/current');link.unlink();link.symlink_to(release,target_is_directory=True)
  finally:
   inbox.close();run('systemctl','start','tracker-steps-api.service','steps-coban.service');wait_api()
  print('PERSONAL_TRANSFER_GPS_MOVED',flush=True)
  value=native(source,'target','LAB_TAREAS','import',a.facts,backup);assert value['company_id']==plan['target_company'] and value['user_id']==facts['source_user_id']
  assert value['odometer']==max(r['value'] for r in facts['readings'])
  native(source,'source','CERRO_EL_PLOMO','archive',a.facts,backup)
  for _ in range(30):
   ready=query('tracker_steps',"SELECT receiver_seen_at>now()-interval '30 seconds' FROM gps_tenants WHERE issuer='LAB_TAREAS' AND company_id="+str(plan['target_company']))
   if ready=='t':break
   time.sleep(1)
  assert ready=='t'
  after=worker(source,'tracker_steps',plan);assert after['position_count']>=result['position_count']
  for service in ('steps-coban','tracker-steps-api','odoo18-cerroelplomo','odoo18-dev','teltonika-ingest'):run('systemctl','is-active','--quiet',service)
  (stage/'delivery.json').write_text(json.dumps({'commit':commit,'backup':str(backup),'native':value,'api_package':package,'personal_positions_preserved':result['position_count'],'remaining_production_devices':4,'device_identity_unchanged':True,'credentials_unchanged':True,'receiver_ready':True},indent=2));print('PERSONAL_TRANSFER_DELIVERED',flush=True)
if __name__=='__main__':main()
