"""Run a versioned, rolling-back probe against a whitelisted disposable clone."""
import argparse
import configparser
import json
from pathlib import Path
import re
import subprocess

HERE = Path(__file__).resolve().parent
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('environment', choices=('development', 'demo', 'cerro'))
parser.add_argument('run_id')
parser.add_argument('probe', choices=('probe_account_fields.py','inspect_legacy_views.py'))
parser.add_argument('--family', choices=('management','payroll'), default='management')
args = parser.parse_args()
assert re.fullmatch('[a-z0-9_]{1,24}', args.run_id)
target = json.loads((HERE / 'environments.json').read_text())['environments'][args.environment]
cfg = configparser.ConfigParser(interpolation=None)
cfg.read(target['config'])
user = subprocess.check_output(['systemctl', 'show', '--value', '--property=User', target['service']], text=True).strip()
source = '/opt/steps-validation/'+args.family+'_' + args.environment + '_' + args.run_id + '/addons'
prefix='MANAGEMENT_QA_' if args.family=='management' else 'PAYROLL_COMPAT_'
database = prefix + args.environment.upper().replace('-','_') + '_' + args.run_id
result = subprocess.run(['sudo', '-u', user, '/usr/bin/python3.10', '/opt/odoo18/odoo-bin', 'shell',
    '-c', target['config'], '-d', database, '--addons-path=' + source + ',' + cfg['options']['addons_path'],
    '--db-filter=^'+database+'$','--no-http', '--workers=0', '--max-cron-threads=0', '--log-level=error'],
    input=(HERE / args.probe).read_text(), text=True, capture_output=True, check=True)
print(result.stdout)
assert 'PROBE_ROLLBACK_OK' in result.stdout
