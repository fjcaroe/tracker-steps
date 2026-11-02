"""Fresh native destination-copy QA, backup and exact-data onboarding only."""
import argparse,configparser,fcntl,hashlib,json,os,pwd,subprocess,time
from pathlib import Path
from datetime import datetime,timezone
def run(*cmd,**kw):return subprocess.run(list(map(str,cmd)),check=True,**kw)
def out(*cmd):return subprocess.check_output(list(map(str,cmd)),text=True).strip()
def native(source,db,facts,root):
 user=pwd.getpwnam('cerro_odoo18');prefix='/tmp/install-native-'+str(time.time_ns());inp=Path(prefix+'-facts.json');result=Path(prefix+'-result.json')
 inp.write_bytes(facts.read_bytes());inp.chmod(0o600);os.chown(inp,user.pw_uid,user.pw_gid)
 try:
  with (source/'tools/gps/install_native_vehicle.py').open('rb') as stdin,(root/(db+'.log')).open('wb') as log:
   run('sudo','-u','cerro_odoo18','env','INSTALLATION_FACTS='+str(inp),'INSTALLATION_RESULT='+str(result),'PYTHONPATH=/opt/odoo18','/usr/bin/python3.10','/opt/odoo18/odoo-bin','shell','-c','/etc/odoo18-cerroelplomo.conf','-d',db,'--db-filter=^'+db+'$','--no-http','--workers=0','--max-cron-threads=0','--logfile=/tmp/'+db+'-install.log',stdin=stdin,stdout=log,stderr=subprocess.STDOUT)
  assert 'INSTALLATION_NATIVE_VEHICLE_OK' in (root/(db+'.log')).read_text()
  return json.loads(result.read_text())
 finally:inp.unlink(missing_ok=True);result.unlink(missing_ok=True)
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['qa','apply']);p.add_argument('source',type=Path);p.add_argument('facts',type=Path);p.add_argument('root',type=Path);a=p.parse_args();assert os.geteuid()==0
 os.umask(0o077);source=a.source.resolve();assert not out('git','-C',source,'status','--porcelain','--untracked-files=no');commit=out('git','-C',source,'rev-parse','HEAD');stage=a.root/commit;stage.mkdir(parents=True,exist_ok=True);stage.chmod(0o700)
 with open('/run/lock/steps-environments.lock','a') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX)
  stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ');dump=stage/(a.action+'-'+stamp+'.dump')
  with dump.open('wb') as f:run('sudo','-u','postgres','pg_dump','-Fc','CERRO_EL_PLOMO',stdout=f)
  run('pg_restore','--file=/dev/null',dump)
  if a.action=='qa':
   assert not (stage/'qa.json').exists();cfg=configparser.ConfigParser(interpolation=None);cfg.read('/etc/odoo18-cerroelplomo.conf');owner=cfg['options']['db_user'];db='INSTALLATION_NATIVE_QA_'+stamp
   run('sudo','-u','postgres','createdb','-O',owner,db)
   try:
    with dump.open('rb') as inp:run('sudo','-u','postgres','pg_restore','--no-owner','--no-acl','--no-comments','--role',owner,'-d',db,stdin=inp)
    run('sudo','-u','postgres','psql','-d',db,'-c','UPDATE ir_cron SET active=false;UPDATE ir_mail_server SET active=false;',stdout=subprocess.DEVNULL)
    result=native(source,db,a.facts,stage);again=native(source,db,a.facts,stage);assert result['vehicle_id']==again['vehicle_id'] and result['link_id']==again['link_id'] and not again['new_vehicle']
    (stage/'qa.json').write_text(json.dumps(dict(commit=commit,facts_sha=hashlib.sha256(a.facts.read_bytes()).hexdigest(),native_models=True,neutralized=True,idempotent=True,source_database='CERRO_EL_PLOMO'),indent=2));print('INSTALLATION_NATIVE_QA_OK',flush=True)
   finally:run('sudo','-u','postgres','dropdb','--if-exists',db)
  else:
   proof=json.loads((stage/'qa.json').read_text());assert proof['commit']==commit and proof['facts_sha']==hashlib.sha256(a.facts.read_bytes()).hexdigest() and proof['idempotent']
   result=native(source,'CERRO_EL_PLOMO',a.facts,stage);(stage/'delivery.json').write_text(json.dumps(dict(commit=commit,result=result,backup=str(dump)),indent=2));print('INSTALLATION_NATIVE_READY linked=True physical_odometer_not_invented=True')
if __name__=='__main__':main()
