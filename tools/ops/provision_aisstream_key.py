"""Provision an explicitly authorized AISStream key over SSH stdin, without logging it."""
import argparse
from pathlib import Path
import re
import subprocess

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--key-file', type=Path, required=True)
p.add_argument('--host', default='odoo-new')
a = p.parse_args()
key = a.key_file.read_text(encoding='utf-8-sig').strip()
assert re.fullmatch(r'[A-Za-z0-9_-]{16,256}', key), 'Expected a file containing only the API key'
remote = '''import fcntl,os,re,sys,tempfile
from pathlib import Path
assert os.geteuid()==0
key=sys.stdin.read().strip()
assert re.fullmatch(r'[A-Za-z0-9_-]{16,256}',key)
with open('/run/lock/steps-environments.lock','a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 p=Path('/etc/steps/aisstream.env')
 p.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
 existing=dict(line.split('=',1) for line in p.read_text().splitlines() if '=' in line and not line.startswith('#')) if p.exists() else {}
 assert not existing.get('AISSTREAM_API_KEY') or existing['AISSTREAM_API_KEY']==key,'A different key exists; explicit rotation required'
 fd,name=tempfile.mkstemp(prefix='.aisstream-',dir=str(p.parent))
 try:
  os.fchmod(fd,0o600)
  with os.fdopen(fd,'w') as f:f.write('AISSTREAM_API_KEY='+key+'\\n');f.flush();os.fsync(f.fileno())
  os.replace(name,p)
 finally:
  if os.path.exists(name):os.unlink(name)
 assert p.stat().st_mode&0o777==0o600
print('AISSTREAM_PRIVATE_KEY_PROVISIONED mode=0600')
'''
# The token is transported only on the encrypted process input, never in argv.
import shlex
result = subprocess.run(['ssh', a.host, 'sudo python3 -c '+shlex.quote(remote)],
                        input=key, text=True, capture_output=True)
if result.returncode:
    raise SystemExit('Private provisioning failed; server output suppressed to protect credentials')
assert result.stdout.strip() == 'AISSTREAM_PRIVATE_KEY_PROVISIONED mode=0600'
print(result.stdout.strip())
