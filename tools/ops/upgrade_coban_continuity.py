"""Receiver-only exact-package rehearsal/upgrade, preserving the private runtime.

No native Odoo/API change, no device command or simulated production position.
Apply checks for a quiet TCP window immediately before its brief restart.
"""
import argparse,fcntl,json,os,shutil,socket,sqlite3,subprocess,time
from pathlib import Path
from datetime import datetime,timezone
from deploy_gps_commissioning import tree as python_tree
from manage_tracker_user_access import tree,sha,query,dump,run,API

BASE=Path('/opt/steps-validation/coban-continuity-20261102')

def history(fence):
 return query('tracker_steps',"SELECT count(*)::text||':'||md5(COALESCE(string_agg(h,'' ORDER BY h),'')) FROM (SELECT md5(row_to_json(p)::text) h FROM gps_positions p WHERE received_at<='"+fence+"'::timestamptz) x")

def tcp_count():
 return max(0,len(subprocess.check_output(['ss','-Hnt','state','established','sport','= :5001'],text=True).splitlines()))

def ready():
 for _ in range(30):
  try:
   with socket.create_connection(('127.0.0.1',5001),timeout=1):pass
   if Path('/run/steps-coban/control.sock').exists():return
  except OSError:pass
  time.sleep(.2)
 raise RuntimeError('Receiver did not become ready')

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['qa','apply']);p.add_argument('source',type=Path);p.add_argument('--runtime-api-root',type=Path);a=p.parse_args();assert os.geteuid()==0;os.umask(0o077)
 source=a.source.resolve();commit=subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD'],text=True).strip();assert not subprocess.check_output(['git','-C',str(source),'status','--porcelain','--untracked-files=no'],text=True).strip()
 stage=BASE/commit;stage.mkdir(parents=True,exist_ok=True);current=Path('/opt/steps-coban/current');cfg=Path('/etc/steps-coban/config.json');unit=Path('/etc/systemd/system/steps-coban.service');config=json.loads(cfg.read_text());database=config['database']
 expected=tree(source/'receivers');api_root=a.runtime_api_root.resolve() if a.runtime_api_root else API
 if a.runtime_api_root:
  assert api_root==Path(subprocess.check_output(['systemctl','show','tracker-steps-api','-p','WorkingDirectory','--value'],text=True).strip()).resolve()
 api=python_tree(api_root/'app')
 if not a.runtime_api_root:assert api==python_tree(source/'backend/tracker_py/app'),'Refuse shared API drift'
 with open('/run/lock/steps-environments.lock','a') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX)
  fence=datetime.now(timezone.utc).isoformat();before=history(fence);baseline=dict(receiver=tree(current.resolve()/'receivers'),config=sha(cfg),unit=sha(unit),api=api)
  if a.action=='qa':
   assert not (stage/'qa.json').exists();db='COBAN_QA_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ');backup=stage/'tracker_steps.dump';dump('tracker_steps',backup);run('sudo','-u','postgres','createdb',db)
   try:
    with backup.open('rb') as inp:run('sudo','-u','postgres','pg_restore','--no-owner','--no-acl','-d',db,stdin=inp)
    with (stage/'receiver-tests.log').open('wb') as log:run('env','PYTHONPATH='+str(source)+':/opt/steps-validation/personal-transfer-test-deps',API/'.venv/bin/python','-m','pytest','receivers/coban/test_receiver.py','receivers/coban/test_starter.py','-q',cwd=source,stdout=log,stderr=subprocess.STDOUT)
    with (stage/'copy-flow.log').open('wb') as log:run('sudo','-u','postgres','env','DATABASE_URL=postgresql+psycopg2:///'+db,'JWT_SECRET=isolated-continuity-copy','PYTHONPATH='+str(source)+':'+str(api_root),API/'.venv/bin/python','-m','receivers.coban.rehearse',cwd=source,stdout=log,stderr=subprocess.STDOUT)
    assert 'COBAN_COPY_QA_OK' in (stage/'copy-flow.log').read_text()
    assert history(fence)==before and python_tree(api_root/'app')==api
    assert tree(current.resolve()/'receivers')==baseline['receiver'] and sha(cfg)==baseline['config'] and sha(unit)==baseline['unit']
    (stage/'qa.json').write_text(json.dumps(dict(commit=commit,baseline=baseline,receiver_after=expected,fresh_copy=True,history_preserved=True,copy_flow=True),indent=2));print('COBAN_CONTINUITY_COPY_QA_OK',flush=True)
   finally:run('sudo','-u','postgres','dropdb','--if-exists',db)
   return
  proof=json.loads((stage/'qa.json').read_text());assert proof['commit']==commit and proof['baseline']==baseline and proof['receiver_after']==expected and proof['copy_flow']
  # Existing installations and permissions remain unchanged, including starter IPC.
  assert config.get('control_socket')=='/run/steps-coban/control.sock'
  deadline=time.monotonic()+35
  while tcp_count():
   if time.monotonic()>deadline:raise RuntimeError('Receiver has live TCP clients; upgrade deferred to avoid interrupting them')
   time.sleep(.5)
  with sqlite3.connect('file:'+database+'?mode=ro',uri=True) as inbox:assert inbox.execute('SELECT count(*) FROM inbox WHERE delivered IS NULL').fetchone()[0]==0,'Pending queue must drain first'
  stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ');backup=stage/('backup-'+stamp);backup.mkdir(mode=0o700);dump('tracker_steps',backup/'tracker_steps.dump');shutil.copy2(cfg,backup/'config.json');shutil.copy2(unit,backup/'unit.service');old=current.resolve();(backup/'receiver-link.txt').write_text(str(old))
  with sqlite3.connect('file:'+database+'?mode=ro',uri=True) as original,sqlite3.connect(backup/'inbox.sqlite') as saved:original.backup(saved)
  release=Path('/opt/steps-coban/releases')/commit
  if not release.exists():shutil.copytree(source/'receivers',release/'receivers',ignore=shutil.ignore_patterns('__pycache__'))
  for path in (release,*release.rglob('*')):path.chmod(0o755 if path.is_dir() else 0o644)
  assert tree(release/'receivers')==expected
  assert tcp_count()==0,'New live client arrived: defer instead of disconnecting it'
  temp=current.with_name('current-continuity-'+str(os.getpid()));assert not temp.exists();run('systemctl','stop','steps-coban')
  try:
   temp.symlink_to(release,target_is_directory=True);os.replace(temp,current);run('systemctl','start','steps-coban');ready();run('systemctl','is-active','--quiet','steps-coban')
   assert tree(current.resolve()/'receivers')==expected and sha(cfg)==baseline['config'] and sha(unit)==baseline['unit'] and python_tree(api_root/'app')==api and history(fence)==before
  except Exception:
   run('systemctl','stop','steps-coban');temp.unlink(missing_ok=True);temp.symlink_to(old,target_is_directory=True);os.replace(temp,current);run('systemctl','start','steps-coban');raise
  (stage/'delivery.json').write_text(json.dumps(dict(commit=commit,backup=str(backup),receiver_after=expected,api_unchanged=True,private_configuration_unchanged=True,history_preserved=True,quiet_tcp_window=True,physical_commands_sent=False),indent=2));print('COBAN_CONTINUITY_PUBLISHED idle_seconds=600 status_without_position=True hardware_orders=0',flush=True)

if __name__=='__main__':main()
