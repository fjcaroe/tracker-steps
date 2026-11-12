"""Create/remove private read-only browser sessions using the registry destination."""
import argparse
import configparser
import json
from pathlib import Path
import subprocess

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('environment', choices=('development','cerro','qa-cerro'))
parser.add_argument('--company-id', type=int)
parser.add_argument('--cleanup', action='store_true')
parser.add_argument('--warehouse-case', action='store_true')
parser.add_argument('--destination-id', type=int)
parser.add_argument('--guide-name')
args = parser.parse_args()
root = Path(__file__).resolve().parent
entry = json.loads((root/'environments.json').read_text())['environments'][args.environment]
config = configparser.ConfigParser(interpolation=None)
config.read(entry['config'])
assert config['options']['db_name'] == entry['database']
user = subprocess.check_output(['systemctl','show','--value','--property=User',entry['service']],text=True).strip()
proof = '/tmp/t207-browser-' + args.environment + '.json'
variables = ['T207_BROWSER_PROOF=' + proof]
if args.company_id:
    variables.append('T207_COMPANY_ID=' + str(args.company_id))
if args.warehouse_case:
    variables.append('T209_WAREHOUSE_CASE=1')
if args.destination_id:
    variables.append('T209_DESTINATION_ID=' + str(args.destination_id))
if args.guide_name:
    variables.append('T209_GUIDE_NAME=' + args.guide_name)
if args.cleanup:
    variables.append('T207_CLEANUP=1')
script = 'import sys\nsys.path.insert(0,' + repr(str(root)) + ')\n' + (root/'t207_browser_session.py').read_text()
result = subprocess.run(['sudo','-u',user,'env',*variables,'/usr/bin/python3.10','/opt/odoo18/odoo-bin','shell',
    '-c',entry['config'],'-d',entry['database'],'--no-http','--workers=0','--max-cron-threads=0','--log-level=error'],
    input=script,text=True,capture_output=True)
assert result.returncode == 0, result.stderr[-2500:]
assert 'T207_BROWSER_SESSION_' in result.stdout
print(result.stdout.strip())
