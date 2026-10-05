"""Remove formatting around the same authenticated key; never create or print a key."""
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import time

import requests

from inspect_sys import process_environment


assert os.geteuid() == 0, 'Run as root'
source = Path('/etc/steps/assistant-demo-sys.env')
assert source.is_file() and not source.is_symlink()
assert source.stat().st_uid == 0 and source.stat().st_mode & 0o777 == 0o600
original = source.read_bytes()
variables = dict(item.split('=', 1) for item in shlex.split(original.decode(), comments=True) if '=' in item)
assert set(variables) == {'OPENAI_API_KEY'}
value = process_environment('odoo18-demo-sys.service').get('OPENAI_API_KEY', '').strip()
assert value and variables['OPENAI_API_KEY'].strip() == value
matches = re.findall(r'sk-[A-Za-z0-9_-]{20,}', value)
assert len(matches) == 1, 'Only an unambiguous formatting repair is allowed'
candidate = matches[0]
response = requests.get('https://api.openai.com/v1/models',
                        headers={'Authorization': 'Bearer ' + candidate},
                        timeout=(5, 20), allow_redirects=False)
assert response.status_code == 200, 'Existing credential must authenticate before repairing formatting'
backup = None
if candidate != value:
    backup = Path('/opt/backups') / ('steps-assistant-key-format-' + time.strftime('%Y%m%dT%H%M%SZ', time.gmtime()))
    backup.mkdir(mode=0o700)
    descriptor = os.open(backup / 'assistant-demo-sys.env.before', os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, 'wb') as output:
        output.write(original)
    temporary = source.with_name('assistant-demo-sys.env.format-repair.tmp')
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, 'w') as output:
        output.write('OPENAI_API_KEY=' + candidate + '\n')
    assert source.read_bytes() == original, 'Environment file changed concurrently'
    os.replace(temporary, source)
reloaded = []
for service in ('odoo18-demo-sys.service', 'odoo18-sys.service'):
    if process_environment(service).get('OPENAI_API_KEY', '').strip() == candidate:
        continue
    subprocess.run(['systemctl', 'restart', service], check=True)
    # Type=simple becomes active before Python exec updates /proc/PID/environ.
    for attempt in range(50):
        if process_environment(service).get('OPENAI_API_KEY', '').strip() == candidate:
            break
        time.sleep(0.1)
    else:
        raise RuntimeError('Service did not load the repaired credential: ' + service)
    reloaded.append(service)
print('EXISTING_KEY_FORMAT_REPAIRED ' + json.dumps({
    'same_underlying_key': True, 'environment': str(source),
    'backup': str(backup) if backup else None, 'reloaded_services': reloaded,
}))
