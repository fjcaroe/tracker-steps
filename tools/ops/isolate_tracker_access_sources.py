"""Materialize byte-identical, environment-owned addon sources without upgrading data."""
import argparse,ast,fcntl,json,os,time
from pathlib import Path
from manage_tracker_user_access import ENVS,MODULES,run,query,tree,config,effective,isolated_overlay

p=argparse.ArgumentParser(description=__doc__);p.add_argument('commit');p.add_argument('receipt',type=Path);a=p.parse_args();assert os.geteuid()==0;os.umask(0o077)
common=Path('/opt/steps-tracker-access/releases')/a.commit/'addons';assert common.is_dir()
a.receipt.mkdir(mode=0o700,parents=True,exist_ok=True)
with open('/run/lock/steps-environments.lock','a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX);proof={}
 for which,(db,user,filename,service) in ENVS.items():
  c=config(which);before={m:tree(effective(c,m)) for m in MODULES};assert all(before[m]==tree(common/m) for m in MODULES)
  target=isolated_overlay(common,which,a.commit)
  for m in MODULES:
   version=ast.literal_eval((target/m/'__manifest__.py').read_text())['version'];assert query(db,"SELECT latest_version FROM ir_module_module WHERE name='"+m+"' AND state='installed'")==version
  path=Path(filename);original=path.read_text();old=str(common)
  if str(target) not in original:
   assert original.count(old)==1
   (a.receipt/(which+'-before.conf')).write_text(original)
   path.write_text(original.replace(old,str(target),1));run('systemctl','restart',service);run('systemctl','is-active','--quiet',service)
  assert all(tree(effective(config(which),m))==before[m] for m in MODULES)
  proof[which]=dict(source=str(target),same_module_bytes=True,data_upgraded=False)
 (a.receipt/'result.json').write_text(json.dumps(proof,indent=2));print('TRACKER_ENVIRONMENT_SOURCES_ISOLATED same_package=True no_data_upgrade=True')
