"""Reproduce an uncommitted archive failure in a disposable clone only."""
import argparse
import configparser
import json
from pathlib import Path
import re
import subprocess

here=Path(__file__).parent
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('run_id')
args=p.parse_args()
assert re.fullmatch('[a-z0-9_]{1,24}',args.run_id)
target=json.loads((here/'environments.json').read_text())['environments']['development']
cfg=configparser.ConfigParser(interpolation=None)
cfg.read(target['config'])
stage=Path('/opt/steps-validation')/('payroll_development_'+args.run_id)
database='PAYROLL_COMPAT_DEVELOPMENT_'+args.run_id
user=subprocess.check_output(['systemctl','show','--value','--property=User',target['service']],text=True).strip()
script='EXPECTED_DATABASE='+repr(database)+'\n'+(here/'transition_payroll.py').read_text()
result=subprocess.run(['sudo','-u',user,'/usr/bin/python3.10','/opt/odoo18/odoo-bin','shell','-c',target['config'],'-d',database,'--db-filter=^'+database+'$','--addons-path='+str(stage/'addons')+','+cfg['options']['addons_path'],'--data-dir='+str(stage/'data'),'--no-http','--workers=0','--max-cron-threads=0','--log-level=error'],input=script,text=True,capture_output=True)
(stage/'retire-diagnostic.log').write_text(result.stdout+result.stderr)
print(result.stdout[-500:])
print(result.stderr[-2300:])
raise SystemExit(result.returncode)
