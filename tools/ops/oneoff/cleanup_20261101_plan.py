import os, pathlib, time, json, re, subprocess, shutil, fcntl
root=pathlib.Path('/opt/steps_backups')
validation=pathlib.Path('/opt/steps-validation')
cut=time.time()-14*86400
refs=[]
for p in pathlib.Path('/proc').glob('[0-9]*'):
    try:
        if int(p.name)==os.getpid(): continue
        refs.append((p/'cmdline').read_bytes().decode(errors='replace'))
        refs.append(os.readlink(p/'cwd'))
        for fd in (p/'fd').iterdir():
            try: refs.append(os.readlink(fd))
            except OSError: pass
    except (OSError,ValueError): pass
for pattern in ('*odoo*.conf','systemd/system/*.service'):
    for p in pathlib.Path('/etc').glob(pattern):
        try: refs.append(p.read_text())
        except OSError: pass
def busy(p): return any(str(p) in r for r in refs)
groups={}
for p in root.iterdir():
    m=re.fullmatch(r'management_(development|cerro|qa-cerro|sys|steps)_(\d{8}T\d{6}Z)',p.name)
    if m and p.is_dir() and not p.is_symlink():
        groups.setdefault(m[1],[]).append(p)
candidates=[]
retained={}
for env, paths in groups.items():
    paths.sort(key=lambda p:p.name,reverse=True)
    retained[env]=[str(p) for p in paths[:2]]
    for p in paths[2:]:
        date=p.name.rsplit('_',1)[1][:8]
        if date<'20261018' and not busy(p): candidates.append(p)
for p in validation.glob('management_*'):
    if not p.is_dir() or p.is_symlink() or p.stat().st_mtime>=cut or busy(p): continue
    d=p/'data'/'filestore'
    if d.is_dir() and not d.is_symlink(): candidates.append(d)
for p in pathlib.Path('/tmp').iterdir():
    if p.is_file() and not p.is_symlink() and p.suffix in ('.tar','.tgz','.zip','.gz') and p.stat().st_mtime<time.time()-7*86400 and not busy(p):
        candidates.append(p)
for p in candidates:
    resolved=p.resolve()
    assert resolved==p and (p.is_relative_to(root) or p.is_relative_to(validation) or p.parent==pathlib.Path('/tmp'))
    assert p.stat().st_dev==pathlib.Path('/').stat().st_dev
plan={'created_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'retained_recent_backups':retained,'candidates':[str(p) for p in candidates]}
pathlib.Path('/var/tmp/steps-cleanup-20261101-plan.json').write_text(json.dumps(plan,indent=2))
print(json.dumps({'counts':{'old_backups':sum(p.is_relative_to(root) for p in candidates),'old_validation_filestores':sum(p.is_relative_to(validation) for p in candidates),'tmp_archives':sum(p.parent==pathlib.Path('/tmp') for p in candidates)},'retained':retained}),flush=True)
sizes=subprocess.check_output(['du','-scB1','--']+[str(p) for p in candidates],text=True)
pathlib.Path('/var/tmp/steps-cleanup-20261101-sizes.txt').write_text(sizes)
print(sizes.splitlines()[-1],flush=True)