"""Run the existing-editor acceptance only inside the certified private T246 copy."""
import argparse
import configparser
import json
from pathlib import Path
import subprocess

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('environment', choices=('development', 'cerro', 'qa-cerro'))
parser.add_argument('stage', type=Path)
args = parser.parse_args()
root = Path(__file__).resolve().parent
stage = args.stage.resolve()
assert stage.parent == Path('/opt/steps-validation')
assert stage.name.startswith('management_' + args.environment + '_t246_')
passed = json.loads((stage / 'qa_passed.json').read_text())
database = passed['database']
assert database.startswith('MANAGEMENT_QA_' + args.environment.upper() + '_t246_')
entry = json.loads((root / 'environments.json').read_text())['environments'][args.environment]
config = configparser.ConfigParser(interpolation=None)
config.read(entry['config'])
assert config['options']['db_name'] == entry['database'] and database != entry['database']
user = subprocess.check_output(['systemctl', 'show', '--value', '--property=User', entry['service']], text=True).strip()
result = subprocess.run(['sudo', '-u', user, '/usr/bin/python3.10', '/opt/odoo18/odoo-bin', 'shell',
    '-c', entry['config'], '-d', database, '--db-filter=^' + database + '$',
    '--addons-path=' + str(stage / 'addons') + ',' + config['options']['addons_path'],
    '--data-dir=' + str(stage / 'data'), '--no-http', '--workers=0', '--max-cron-threads=0', '--log-level=critical'],
    input=(root / 'verify_received_producer_business.py').read_text(), text=True, capture_output=True)
(stage / 'existing-business-flow.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0 and 'T246_EXISTING_BUSINESS_FLOW_OK' in result.stdout, result.stderr[-2400:]
print('\n'.join(line for line in result.stdout.splitlines() if line.startswith('T246_EXISTING_BUSINESS_FLOW_OK')))
