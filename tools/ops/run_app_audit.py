"""Run read-only effective-form audits through the exact configured database."""
import argparse
import configparser
import json
from pathlib import Path
import subprocess

here=Path(__file__).parent
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('environment',choices=('development','cerro','demo-sys','steps','sys'))
args=p.parse_args()
target=json.loads((here/'environments.json').read_text())['environments'][args.environment]
cfg=configparser.ConfigParser(interpolation=None)
cfg.read(target['config'])
user=subprocess.check_output(['systemctl','show','--value','--property=User',target['service']],text=True).strip()
result=subprocess.run(['sudo','-u',user,'/usr/bin/python3.10','/opt/odoo18/odoo-bin','shell','-c',target['config'],'-d',target['database'],'--db-filter=^'+target['database']+'$','--no-http','--workers=0','--max-cron-threads=0','--log-level=error'],input=(here/'audit_app_views.py').read_text(),text=True,capture_output=True,check=True)
assert 'APP_AUDIT_OK' in result.stdout, result.stderr[-1800:]
print(result.stdout)
