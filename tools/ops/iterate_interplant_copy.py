"""Iterate T207/T208 tests only in an existing disposable copy, never certify it."""
import argparse
import configparser
import fcntl
import json
import re
import subprocess
import socket
from pathlib import Path
import manage_management

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('run_id')
parser.add_argument('release', type=Path)
args = parser.parse_args()
assert re.fullmatch('[a-z0-9_]{1,24}', args.run_id)
database = 'MANAGEMENT_QA_DEVELOPMENT_' + args.run_id
stage = Path('/opt/steps-validation/management_development_' + args.run_id)
assert (stage / 'baseline.json').is_file() and not (stage / 'qa_passed.json').exists()
registry = json.loads((Path(__file__).parent / 'environments.json').read_text())
target = registry['environments']['development']
assert database != target['database']
config = configparser.ConfigParser(interpolation=None)
config.read(target['config'])
source = stage / ('iteration_' + str(len(list(stage.glob('iteration_*')))))
source.mkdir()
manage_management.MODULES = ('step_packing_ticket_revision', 'step_packing_interplant')
proof = manage_management.extract(args.release, source)
assert set(proof['versions']) == set(manage_management.MODULES)
user = subprocess.check_output(['systemctl', 'show', '--value', '--property=User', target['service']], text=True).strip()
subprocess.run(['chown', '-R', user, str(source)], check=True)
log = source / 'tests.log'
with open('/run/lock/steps-environments.lock', 'a') as lock:
    fcntl.flock(lock, fcntl.LOCK_EX)
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        port = listener.getsockname()[1]
    result = subprocess.run(['sudo', '-u', user, '/usr/bin/python3.10', '/opt/odoo18/odoo-bin',
        '-c', target['config'], '-d', database, '--db-filter=^' + database + '$',
        '--addons-path=' + str(source) + ',' + config['options']['addons_path'],
        '--data-dir=' + str(stage / 'data'), '--no-http', '--workers=0', '--max-cron-threads=0',
        '--http-interface=127.0.0.1', '--http-port=' + str(port), '--gevent-port=0',
        '--without-demo=all', '-i', 'step_packing_interplant', '-u', 'step_packing_ticket_revision,step_packing_interplant',
        '--test-enable', '--test-tags=/step_packing_interplant,/step_packing_ticket_revision:ReceiptStatusCase',
        '--stop-after-init', '--logfile=' + str(log)], capture_output=True, text=True)
print('DIAGNOSTIC_ONLY_NO_CERTIFICATION log=' + str(log))
text = log.read_text(errors='replace')
for line in text.splitlines():
    if any(marker in line for marker in ('tests.result', ' ERROR ', ' FAIL', 'Traceback')):
        print(line)
if result.returncode:
    print((result.stdout + result.stderr)[-2000:])
raise SystemExit(result.returncode)
