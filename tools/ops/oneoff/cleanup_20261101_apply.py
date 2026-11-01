import sys
if '--execute-20261101-plan' not in sys.argv:
    raise SystemExit('One-off destructive maintenance. Requires the reviewed 20261101 plan and --execute-20261101-plan.')
import pathlib,json,os,subprocess,fcntl,shutil,time
lock=open('/run/lock/steps-environments.lock','a')
fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
plan=json.loads(pathlib.Path('/var/tmp/steps-cleanup-20261101-plan.json').read_text())
verified=[]
for env, paths in plan['retained_recent_backups'].items():
    for name in paths:
        p=pathlib.Path(name)/'database.dump'
        assert p.is_file() and p.stat().st_size>0, str(p)
        subprocess.run(['pg_restore','-f','/dev/null',str(p)],check=True,stdout=subprocess.DEVNULL)
        verified.append(str(p))
print('Verified retained dumps: '+str(len(verified)),flush=True)
refs=[]
for p in pathlib.Path('/proc').glob('[0-9]*'):
    try:
        if int(p.name)==os.getpid() or (p/'comm').read_text().strip() in ('du','find'): continue
        refs.append((p/'cmdline').read_bytes().decode(errors='replace'))
        refs.append(os.readlink(p/'cwd'))
        for fd in (p/'fd').iterdir():
            try: refs.append(os.readlink(fd))
            except OSError: pass
    except (OSError,ValueError): pass
before=os.statvfs('/')
removed=[]; skipped=[]
for name in plan['candidates']:
    p=pathlib.Path(name)
    assert p.resolve()==p and (p.is_relative_to('/opt/steps_backups') or p.is_relative_to('/opt/steps-validation') or p.parent==pathlib.Path('/tmp'))
    if not p.exists(): skipped.append([name,'absent']); continue
    if any(name in r for r in refs): skipped.append([name,'active reference']); continue
    if p.is_dir():
        newest=max((os.lstat(os.path.join(d,n)).st_mtime for d,ds,fs in os.walk(p) for n in ds+fs),default=p.stat().st_mtime)
        if newest>time.time()-14*86400:
            skipped.append([name,'recent descendant']); continue
        shutil.rmtree(p)
    else: p.unlink()
    removed.append(name)
    if len(removed)%25==0: print('Removed '+str(len(removed)),flush=True)
after=os.statvfs('/')
result={'verified_dumps':verified,'removed':removed,'skipped':skipped,'bytes_reclaimed':(after.f_bavail-before.f_bavail)*after.f_frsize,'free_bytes':after.f_bavail*after.f_frsize}
pathlib.Path('/var/tmp/steps-cleanup-20261101-result.json').write_text(json.dumps(result,indent=2))
print(json.dumps({k:v for k,v in result.items() if k not in ('verified_dumps','removed','skipped')}),flush=True)
print('removed='+str(len(removed))+' skipped='+str(len(skipped)),flush=True)