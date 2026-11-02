"""Exact overlays, destination-copy QA and scoped Tracker access publication."""
import argparse, ast, configparser, fcntl, hashlib, json, os, pwd, shutil, subprocess, time, sqlite3
from urllib.request import urlopen
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

def isolated_overlay(common, which, commit):
 assert which in ENVS and re.fullmatch('[0-9a-f]{40}',commit)
 target=Path('/opt/steps-tracker-access/releases')/which/commit/'addons'
 if not target.exists():
  target.mkdir(parents=True)
  for module in MODULES:shutil.copytree(common/module,target/module,ignore=shutil.ignore_patterns('__pycache__'))
 for path in (target.parent.parent,target.parent,target,*target.rglob('*')):path.chmod(0o755 if path.is_dir() else 0o644)
 assert all(tree(common/m)==tree(target/m) for m in MODULES)
 return target

def ready_api(port):
 for _ in range(40):
  try:
   with urlopen('http://127.0.0.1:'+str(port)+'/openapi.json',timeout=2) as r:paths=json.load(r)['paths']
   assert '/mobile/services' in paths and '/v1/assets/{asset_id}/starter-control/commands' in paths
   return
  except (OSError,AssertionError):time.sleep(.5)
 raise RuntimeError('API release did not become ready')

def migration(source, db):
 path=source/'backend/tracker_py/migrations/20261102_starter_relay.up.sql'
 if path.exists():query(db,path.read_text())

def dist_files(source):
 return {str(p.relative_to(source/'dist')):hashlib.sha256(p.read_bytes()).hexdigest() for p in (source/'dist').rglob('*') if p.is_file()}

def snippet(which):
 return Path('/etc/nginx/snippets/steps-tracker-'+('dev' if which=='development' else 'cerro')+'-gps.conf')

def frontend(source, which, commit, proof, backup):
 target=Path('/var/www/steps-tracker-releases')/commit
 if not target.exists():shutil.copytree(source/'dist',target)
 for p in [target,*target.rglob('*')]:p.chmod(0o755 if p.is_dir() else 0o644)
 assert dist_files(source)==proof['dist']
 conf=snippet(which);assert sha(conf)==proof['snippets'][which],'Concurrent frontend change';old=conf.read_text();roots=set(re.findall(r'/var/www/steps-tracker-releases/[a-f0-9]{40}',old));assert len(roots)==1
 shutil.copy2(conf,backup/(which+'-frontend.conf'));conf.write_text(old.replace(next(iter(roots)),str(target)));run('nginx','-t');run('systemctl','reload','nginx')
 host='desarrollo.stepsapp.cl' if which=='development' else 'cerroelplomo.stepsapp.cl'
 for _ in range(30):
  with urlopen('https://'+host+'/web_tracker/',timeout=15) as r:matched=r.read()==(source/'dist/index.html').read_bytes()
  if matched:break
  time.sleep(.5)
 assert matched
 for name,digest in proof['dist'].items():
  with urlopen('https://'+host+'/web_tracker/'+name,timeout=15) as r:assert hashlib.sha256(r.read()).hexdigest()==digest

def receiver_release(source,commit,proof,backup):
 current=Path('/opt/steps-coban/current');assert tree(current.resolve()/'receivers')==proof['receiver_before']
 cfg=Path('/etc/steps-coban/config.json');unit=Path('/etc/systemd/system/steps-coban.service')
 assert sha(cfg)==proof['receiver_config'] and sha(unit)==proof['receiver_unit']
 shutil.copy2(cfg,backup/'receiver-config.json');shutil.copy2(unit,backup/'receiver-unit.service');(backup/'receiver-link.txt').write_text(str(current.resolve()))
 release=Path('/opt/steps-coban/releases')/commit
 if not release.exists():shutil.copytree(source/'receivers',release/'receivers',ignore=shutil.ignore_patterns('__pycache__'))
 for p in [release,*release.rglob('*')]:p.chmod(0o755 if p.is_dir() else 0o644)
 run('systemctl','stop','steps-coban')
 try:
  config_data=json.loads(cfg.read_text())
  with sqlite3.connect('file:'+config_data['database']+'?mode=ro',uri=True) as original,sqlite3.connect(backup/'receiver-inbox.sqlite') as saved:original.backup(saved)
  api_user=subprocess.check_output(['systemctl','show','tracker-steps-api','-p','User','--value'],text=True).strip()
  config_data.update(control_socket='/run/steps-coban/control.sock',control_uid=pwd.getpwnam(api_user).pw_uid);cfg.write_text(json.dumps(config_data,indent=2))
  shutil.copy2(source/'receivers/coban/steps-coban.service',unit);run('systemctl','daemon-reload');current.unlink();current.symlink_to(release,target_is_directory=True)
 finally:run('systemctl','start','steps-coban')
 run('systemctl','is-active','--quiet','steps-coban')
 assert tree(current.resolve()/'receivers')==tree(source/'receivers')

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
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['qa','development','production','configure','configure-development']);p.add_argument('source',type=Path);p.add_argument('facts',type=Path);a=p.parse_args();assert os.geteuid()==0;os.umask(0o077)
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
   assert not (stage/'qa.json').exists();proof={'commit':commit,'facts_sha':sha(a.facts),'environments':{},'fleet_before':sha(API/'app/routers/fleet.py'),'fleet_after':sha(source/'backend/tracker_py/app/routers/fleet.py'), 'api_before':api_files(API/'app'), 'api_after':api_files(source/'backend/tracker_py/app'), 'dist':dist_files(source),'snippets':{k:sha(snippet(k)) for k in ('development','cerro')}, 'receiver_before':tree(Path('/opt/steps-coban/current').resolve()/'receivers'),'receiver_config':sha('/etc/steps-coban/config.json'),'receiver_unit':sha('/etc/systemd/system/steps-coban.service')}
   assert 'index.html' in proof['dist']
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
    run('env','PYTHONPATH='+str(source)+':/opt/steps-validation/personal-transfer-test-deps',API/'.venv/bin/python','-m','pytest','receivers/coban/test_receiver.py','receivers/coban/test_starter.py','-q',cwd=source,stdout=log,stderr=subprocess.STDOUT)
   (stage/'qa.json').write_text(json.dumps(proof,indent=2));print('TRACKER_ACCESS_QA_OK',flush=True);return
  proof=json.loads((stage/'qa.json').read_text());assert proof['commit']==commit and proof['facts_sha']==sha(a.facts)
  if a.action in ('configure','configure-development'):
   for which in (('development',) if a.action=='configure-development' else ('development','cerro')):
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
      if (source/'backend/tracker_py/app'/name).exists():
       shutil.copyfile(source/'backend/tracker_py/app'/name,target/name);(target/name).chmod(0o644)
    finally:run('systemctl','start',service)
    run('systemctl','is-active','--quiet',service)
    ready_api(8000 if service=='tracker-steps-api' else 8012)
   receiver_release(source,commit,proof,backup)
  assert sha(API/'app/routers/fleet.py')==proof['fleet_after']
  for which in scopes:
   db,user,conf,service=ENVS[which];run('systemctl','stop',service)
   try:
    c=config(which);c['options']['addons_path']=str(isolated_overlay(overlay,which,commit))+','+c['options']['addons_path']
    with Path(conf).open('w') as f:c.write(f)
    upgrade(which,db,conf,stage)
   finally:run('systemctl','start',service)
   run('systemctl','is-active','--quiet',service)
  frontend(source,'development' if a.action=='development' else 'cerro',commit,proof,backup)
  (stage/(a.action+'.json')).write_text(json.dumps(dict(commit=commit,backup=str(backup),scopes=scopes),indent=2));print('TRACKER_ACCESS_PUBLISHED '+a.action,flush=True)
if __name__=='__main__':main()
