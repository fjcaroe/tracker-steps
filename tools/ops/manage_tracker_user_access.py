"""Exact overlays, destination-copy QA and scoped Tracker access publication."""
import argparse, ast, configparser, fcntl, hashlib, json, os, pwd, shutil, subprocess, time
from datetime import datetime, timezone
from pathlib import Path
from contextlib import contextmanager
import re

ENVS = {
 'development': ('LAB_TAREAS','odoo','/etc/dev_odoo18.conf','odoo18-dev'),
 'cerro': ('CERRO_EL_PLOMO','cerro_odoo18','/etc/odoo18-cerroelplomo.conf','odoo18-cerroelplomo'),
 'qa-cerro': ('QA-CERROELPLOMO','cerroqa_odoo18','/etc/odoo18-qa-cerroelplomo.conf','odoo18-qa-cerroelplomo'),
}
API = Path('/opt/fernando_odoo18/apis/backend/tracker_py')
BASE = Path('/opt/steps-validation/tracker-user-access-20261102')
MODULES = ('step_tracker_portal','step_tracker_vehicle_access')
API_FILES = ('main.py','models/fleet.py','routers/fleet.py','routers/fleet_configuration.py','routers/starter_control.py')

def api_files(root):
 return {f:sha(root/f) if (root/f).exists() else None for f in API_FILES}

def migration(source, db):
 path=source/'backend/tracker_py/migrations/20261102_starter_relay.up.sql'
 if path.exists():query(db,path.read_text())

@contextmanager
def qa_socket(which, database, stage):
 if which != 'qa-cerro':
  yield
  return
 assert re.fullmatch(r'TRACKER_ACCESS_QA_qa_cerro_\d+', database)
 hba=Path(query('postgres','SHOW hba_file'));assert str(hba).startswith('/etc/postgresql/')
 original=hba.read_text();block='# STEPS TEMPORARY TRACKER CLONE '+database+'\nlocal "'+database+'" cerroqa_odoo18 md5\n'
 (stage/'qa-hba-before.conf').write_text(original)
 try:
  hba.write_text(block+original);assert not query('postgres','SELECT error FROM pg_hba_file_rules WHERE error IS NOT NULL');query('postgres','SELECT pg_reload_conf()');yield
 finally:
  current=hba.read_text();assert block in current;hba.write_text(current.replace(block,'',1));query('postgres','SELECT pg_reload_conf()')

def run(*args, **kw):
 return subprocess.run(list(map(str,args)),check=True,**kw)

def sha(path):
 return hashlib.sha256(Path(path).read_bytes().replace(b'\r\n',b'\n')).hexdigest()

def tree(root):
 return {str(p.relative_to(root)):sha(p) for p in root.rglob('*') if p.is_file() and '__pycache__' not in p.parts}

def query(db, sql):
 return subprocess.check_output(['sudo','-u','postgres','psql','-v','ON_ERROR_STOP=1','-At','-d',db],input=sql,text=True).strip()

def dump(db, path):
 with path.open('wb') as f:run('sudo','-u','postgres','pg_dump','-Fc',db,stdout=f)
 run('pg_restore','--file=/dev/null',path)

def config(which):
 c=configparser.ConfigParser(interpolation=None);c.read(ENVS[which][2]);assert c['options']['db_name']==ENVS[which][0];return c

def effective(c, module):
 return next(Path(p.strip())/module for p in c['options']['addons_path'].split(',') if (Path(p.strip())/module/'__manifest__.py').exists())

def baseline(which):
 c=config(which);return {'config':sha(ENVS[which][2]),'portal':tree(effective(c,'step_tracker_portal'))}

def native(source, which, db, conf, facts, mode, stage):
 u=pwd.getpwnam(ENVS[which][1]);stamp=str(time.time_ns());inp=Path('/tmp/tracker-access-facts-'+stamp+'.json');out=Path('/tmp/tracker-access-result-'+stamp+'.json');inp.write_bytes(facts.read_bytes());inp.chmod(0o600);os.chown(inp,u.pw_uid,u.pw_gid)
 try:
  with (source/'tools/qa/tracker/vehicle-access-native.py').open('rb') as code,(stage/(which+'-'+mode+'-'+stamp+'.log')).open('wb') as log:
   run('sudo','-u',u.pw_name,'env','TRACKER_ACCESS_MODE='+mode,'TRACKER_ACCESS_FACTS='+str(inp),'TRACKER_ACCESS_RESULT='+str(out),'PYTHONPATH=/opt/odoo18','/usr/bin/python3.10','/opt/odoo18/odoo-bin','shell','-c',conf,'-d',db,'--db-filter=^'+db+'$','--no-http','--workers=0','--max-cron-threads=0','--logfile=/tmp/tracker-access-'+which+'.log',stdin=code,stdout=log,stderr=subprocess.STDOUT)
  return json.loads(out.read_text()) if out.exists() else {}
 finally:inp.unlink(missing_ok=True);out.unlink(missing_ok=True)

def upgrade(which, db, conf, stage):
 with (stage/(which+'-upgrade-'+str(time.time_ns())+'.log')).open('wb') as log:
  run('sudo','-u',ENVS[which][1],'/usr/bin/python3.10','/opt/odoo18/odoo-bin','-c',conf,'-d',db,'--db-filter=^'+db+'$','-u','step_tracker_portal','-i','step_tracker_vehicle_access','--stop-after-init','--no-http','--workers=0','--max-cron-threads=0','--logfile=/dev/stdout',stdout=log,stderr=subprocess.STDOUT)
 assert query(db,"SELECT count(*) FROM ir_module_module WHERE name IN ('step_tracker_portal','step_tracker_vehicle_access') AND state='installed'")=='2'

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['qa','development','production','configure']);p.add_argument('source',type=Path);p.add_argument('facts',type=Path);a=p.parse_args();assert os.geteuid()==0;os.umask(0o077)
 source=a.source.resolve();commit=subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD'],text=True).strip();assert not subprocess.check_output(['git','-C',str(source),'status','--porcelain','--untracked-files=no'],text=True).strip()
 stage=BASE/commit;stage.mkdir(parents=True,exist_ok=True);stage.chmod(0o700);facts=json.loads(a.facts.read_text());overlay=Path('/opt/steps-tracker-access/releases')/commit/'addons'
 if not overlay.exists():
  overlay.mkdir(parents=True)
  for m in MODULES:shutil.copytree(source/m,overlay/m,ignore=shutil.ignore_patterns('__pycache__'))
  for f in [overlay.parent,overlay,*overlay.rglob('*')]:f.chmod(0o755 if f.is_dir() else 0o644)
  for f in (Path('/opt/steps-tracker-access'),Path('/opt/steps-tracker-access/releases')):f.chmod(0o755)
 assert all(tree(source/m)==tree(overlay/m) for m in MODULES)
 with open('/run/lock/steps-environments.lock','a') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX)
  if a.action=='qa':
   assert not (stage/'qa.json').exists();proof={'commit':commit,'facts_sha':sha(a.facts),'environments':{},'fleet_before':sha(API/'app/routers/fleet.py'),'fleet_after':sha(source/'backend/tracker_py/app/routers/fleet.py'), 'api_before':api_files(API/'app'), 'api_after':api_files(source/'backend/tracker_py/app')}
   for which,(db,user,conf,service) in ENVS.items():
    print('TRACKER_ACCESS_COPY '+which,flush=True);proof['environments'][which]=baseline(which);backup=stage/(which+'.dump');dump(db,backup);c=config(which);clone='TRACKER_ACCESS_QA_'+which.replace('-','_')+'_'+str(int(time.time()));run('sudo','-u','postgres','createdb','-O',c['options']['db_user'],clone)
    temp=Path('/tmp/tracker-access-qa-'+which+'.conf');fp=Path('/tmp/tracker-access-qa-'+which+'.json')
    try:
     with backup.open('rb') as f:run('sudo','-u','postgres','pg_restore','--no-owner','--no-acl','--no-comments','--role',c['options']['db_user'],'-d',clone,stdin=f,stdout=subprocess.DEVNULL)
     query(clone,'UPDATE ir_cron SET active=false;UPDATE ir_mail_server SET active=false;');before=query(clone,'SELECT count(*) FROM fleet_vehicle')
     c['options']['db_name']=clone;c['options']['addons_path']=str(overlay)+','+c['options']['addons_path']
     with temp.open('w') as f:c.write(f)
     fp.write_text(json.dumps(facts[which]));u=pwd.getpwnam(user)
     for path in (temp,fp):path.chmod(0o600);os.chown(path,u.pw_uid,u.pw_gid)
     with qa_socket(which,clone,stage):
      upgrade(which,clone,temp,stage);native(source,which,clone,temp,fp,'qa',stage)
     assert before==query(clone,'SELECT count(*) FROM fleet_vehicle')
    finally:
     temp.unlink(missing_ok=True);fp.unlink(missing_ok=True);run('sudo','-u','postgres','dropdb','--if-exists',clone)
   gps='TRACKER_ACCESS_GPS_QA_'+str(int(time.time()));backup=stage/'tracker_steps.dump';dump('tracker_steps',backup);run('sudo','-u','postgres','createdb',gps)
   fp=Path('/tmp/tracker-access-gps-copy.json');fp.write_text(json.dumps(facts['cerro']));fp.chmod(0o600);os.chown(fp,pwd.getpwnam('postgres').pw_uid,pwd.getpwnam('postgres').pw_gid)
   try:
    with backup.open('rb') as f:run('sudo','-u','postgres','pg_restore','--no-owner','--no-acl','-d',gps,stdin=f)
    from deploy_gps_commissioning import columns,snapshot
    cols=columns(gps);before=snapshot(gps,cols);migration(source,gps);migration(source,gps);assert snapshot(gps,cols)==before
    with (stage/'gps-copy.log').open('wb') as log:
     run('sudo','-u','postgres','env','DATABASE_URL=postgresql+psycopg2:///'+gps,'JWT_SECRET=copy-only','TRACKER_ACCESS_FACTS='+str(fp),'PYTHONPATH='+str(source/'backend/tracker_py')+':/opt/steps-validation/personal-transfer-test-deps',API/'.venv/bin/python',source/'tools/qa/tracker/vehicle-access-copy.py',stdout=log,stderr=subprocess.STDOUT)
   finally:fp.unlink(missing_ok=True);run('sudo','-u','postgres','dropdb','--if-exists',gps)
   # API tests use fixtures only, never issue actuator commands or write active databases.
   with (stage/'api-tests.log').open('wb') as log:
    run('env','DATABASE_URL=sqlite://','JWT_SECRET=copy-only','PYTHONPATH='+str(source/'backend/tracker_py')+':/opt/steps-validation/personal-transfer-test-deps',API/'.venv/bin/python','-m','pytest','tests/test_fleet.py','tests/test_vehicle_scope.py','tests/test_receiver.py','tests/test_starter_control.py','-q',cwd=source/'backend/tracker_py',stdout=log,stderr=subprocess.STDOUT)
   with (stage/'receiver-tests.log').open('wb') as log:
    run(API/'.venv/bin/python','-m','pytest','receivers/coban/test_receiver.py','receivers/coban/test_starter.py','-q',cwd=source,stdout=log,stderr=subprocess.STDOUT)
   (stage/'qa.json').write_text(json.dumps(proof,indent=2));print('TRACKER_ACCESS_QA_OK',flush=True);return
  proof=json.loads((stage/'qa.json').read_text());assert proof['commit']==commit and proof['facts_sha']==sha(a.facts)
  if a.action=='configure':
   for which in ('development','cerro'):
    assert (stage/('development.json' if which=='development' else 'production.json')).exists()
    dump(ENVS[which][0],stage/(which+'-pre-users-'+str(int(time.time()))+'.dump'))
    fp=Path('/tmp/tracker-access-configure-'+which+'.json');fp.write_text(json.dumps(facts[which]));fp.chmod(0o600)
    try:result=native(source,which,ENVS[which][0],ENVS[which][2],fp,'configure',stage);(stage/(which+'-users.json')).write_text(json.dumps(result,indent=2))
    finally:fp.unlink(missing_ok=True)
   print('TRACKER_ACCESS_USERS_CONFIGURED',flush=True);return
  scopes=('development',) if a.action=='development' else ('cerro','qa-cerro')
  if a.action=='production':assert (stage/'development.json').exists()
  stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ');backup=stage/('backup-'+a.action+'-'+stamp);backup.mkdir(mode=0o700)
  for which in scopes:
   assert baseline(which)==proof['environments'][which],'Concurrent Odoo configuration/source change'
   dump(ENVS[which][0],backup/(which+'.dump'));shutil.copy2(ENVS[which][2],backup/(which+'.conf'))
  if a.action=='development':
   for target,service,db in ((API/'app','tracker-steps-api','tracker_steps'),(Path('/opt/steps-tracker-development/current/backend/tracker_py/app'),'steps-tracker-dev-api','tracker_steps_development')):
    assert api_files(target)==proof['api_before'],'Unexpected API baseline';dump(db,backup/(db+'.dump'));shutil.copytree(target,backup/(service+'-app'),ignore=shutil.ignore_patterns('__pycache__'));run('systemctl','stop',service)
    try:
     migration(source,db)
     for name in API_FILES:
      if (source/'backend/tracker_py/app'/name).exists():shutil.copyfile(source/'backend/tracker_py/app'/name,target/name)
    finally:run('systemctl','start',service)
    run('systemctl','is-active','--quiet',service)
  assert sha(API/'app/routers/fleet.py')==proof['fleet_after']
  for which in scopes:
   db,user,conf,service=ENVS[which];run('systemctl','stop',service)
   try:
    c=config(which);c['options']['addons_path']=str(overlay)+','+c['options']['addons_path']
    with Path(conf).open('w') as f:c.write(f)
    upgrade(which,db,conf,stage)
   finally:run('systemctl','start',service)
   run('systemctl','is-active','--quiet',service)
  (stage/(a.action+'.json')).write_text(json.dumps(dict(commit=commit,backup=str(backup),scopes=scopes),indent=2));print('TRACKER_ACCESS_PUBLISHED '+a.action,flush=True)
if __name__=='__main__':main()
