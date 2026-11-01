"""Bounded shared lease for browser review while other release jobs are queued."""
import fcntl,os,sys,time
from pathlib import Path
assert os.geteuid()==0
ready,release=map(Path,sys.argv[1:3]);assert ready.parent==release.parent==Path('/tmp')
assert not ready.exists() and not release.exists();os.umask(0o077)
with open('/run/lock/steps-environments.lock','a') as lock:
 fcntl.flock(lock,fcntl.LOCK_SH)
 try:
  ready.write_text(str(os.getpid()));print('PERSONAL_REVIEW_LEASE_READY',flush=True)
  deadline=time.monotonic()+300
  while not release.exists() and time.monotonic()<deadline:time.sleep(1)
 finally:ready.unlink(missing_ok=True);release.unlink(missing_ok=True)
print('PERSONAL_REVIEW_LEASE_RELEASED',flush=True)
