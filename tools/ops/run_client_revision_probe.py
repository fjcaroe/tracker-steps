"""Run a metadata-only client revision inspection via the canonical environment registry."""
import argparse
import configparser
import json
from pathlib import Path
import subprocess

here = Path(__file__).resolve().parent
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('environment', choices=('development', 'cerro'))
p.add_argument('--probe', choices=('inspect_client_revision.py', 'inspect_gantt_support.py'), default='inspect_client_revision.py')
args = p.parse_args()
target = json.loads((here/'environments.json').read_text())['environments'][args.environment]
cfg = configparser.ConfigParser(interpolation=None); cfg.read(target['config'])
opts = cfg['options']
assert opts['db_name'] == target['database'] and int(opts['http_port']) == target['port']
user = subprocess.check_output(['systemctl','show','--value','--property=User',target['service']],text=True).strip()
print('ENVIRONMENT', args.environment, target['database'], opts['addons_path'], flush=True)
result = subprocess.run(['sudo','-u',user,'/usr/bin/python3.10','/opt/odoo18/odoo-bin','shell','-c',target['config'],
    '-d',target['database'],'--no-http','--workers=0','--max-cron-threads=0','--log-level=error'],
    input=(here/args.probe).read_text(),text=True,capture_output=True)
print(result.stdout)
print(result.stderr[-4000:])
assert result.returncode == 0
