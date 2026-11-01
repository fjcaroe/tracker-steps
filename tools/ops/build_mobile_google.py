"""Build the mobile Google monitor with the existing public browser Maps key.

Never copies backend credentials or other VITE variables. Run in a fresh server
checkout; the private environment remains untracked and is never printed.
"""
from pathlib import Path
import os
import subprocess
import sys

source = Path(sys.argv[1]).resolve()
values = {}
for filename in ('.env', '.env.production'):
    for line in (Path('/opt/fernando_odoo18/apis/tracker-steps') / filename).read_text().splitlines():
        name, separator, value = line.strip().partition('=')
        if separator and name == 'VITE_GOOGLE_MAPS_API_KEY':
            values[name] = value.strip().strip('\"\'')
key = values.get('VITE_GOOGLE_MAPS_API_KEY')
assert key and '\n' not in key and key.startswith('AIza'), 'Existing browser Maps key unavailable'
envfile = source / 'mobile/.env.tracker.local'
envfile.write_text('VITE_GOOGLE_MAPS_API_KEY=' + key + '\n')
os.chmod(envfile, 0o600)
for command in (['npm','ci','--no-audit','--no-fund'], ['npm','test'], ['npm','run','build:tracker']):
    subprocess.run(command, cwd=source/'mobile', check=True)
print('MOBILE_GOOGLE_BUILD_OK existing_browser_key=True')
