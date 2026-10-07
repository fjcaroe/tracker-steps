"""Run a private, rolling-back payroll probe against a registry-selected DB."""
import argparse
import configparser
import json
from pathlib import Path
import re
import subprocess

HERE = Path(__file__).resolve().parent
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('environment', choices=('development', 'sys'))
p.add_argument('cases', type=Path)
p.add_argument('--run-id')
p.add_argument('--output', type=Path, required=True)
args = p.parse_args()
target = json.loads((HERE/'environments.json').read_text())['environments'][args.environment]
cfg = configparser.ConfigParser(interpolation=None); cfg.read(target['config'])
opts = cfg['options']
database = target['database']
paths = opts['addons_path']
data = opts['data_dir']
if args.run_id:
    assert re.fullmatch('[a-z0-9_]{1,24}', args.run_id)
    stage = Path('/opt/steps-validation') / ('management_' + args.environment + '_' + args.run_id)
    database = 'MANAGEMENT_QA_' + args.environment.upper() + '_' + args.run_id
    paths = str(stage/'addons') + ',' + paths
    data = str(stage/'data')
user = subprocess.check_output(['systemctl','show','--value','--property=User',target['service']],text=True).strip()
script = 'CASES=' + repr(json.loads(args.cases.read_text())) + '\n' + (HERE/'check_payroll_ticket_flows.py').read_text()
result = subprocess.run(['sudo','-u',user,'/usr/bin/python3.10','/opt/odoo18/odoo-bin','shell',
                         '-c',target['config'],'-d',database,'--addons-path='+paths,'--data-dir='+data,
                         '--db-filter=^'+database+'$','--no-http','--workers=0','--max-cron-threads=0','--log-level=error'],
                        input=script,text=True,capture_output=True)
args.output.parent.mkdir(parents=True,exist_ok=True)
args.output.write_text(result.stdout + result.stderr)
assert result.returncode == 0 and 'PROBE_ROLLBACK_OK' in result.stdout, 'Read private probe log: '+str(args.output)
print('TICKET_PROBE_OK database=' + database + ' output=' + str(args.output))
