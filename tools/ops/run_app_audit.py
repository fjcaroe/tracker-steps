"""Run read-only effective-form audits through the exact configured database."""
import argparse
import configparser
import json
from pathlib import Path
import subprocess

here=Path(__file__).parent
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('environment',choices=('development','cerro','demo-sys','steps','sys'))
p.add_argument('--studio', action='store_true', help='Read Studio/Python ownership and actual menu views')
args=p.parse_args()
target=json.loads((here/'environments.json').read_text())['environments'][args.environment]
cfg=configparser.ConfigParser(interpolation=None)
cfg.read(target['config'])
user=subprocess.check_output(['systemctl','show','--value','--property=User',target['service']],text=True).strip()
source = 'audit_studio_dependencies.py' if args.studio else 'audit_app_views.py'
result=subprocess.run(['sudo','-u',user,'nice','-n','15','/usr/bin/python3.10','/opt/odoo18/odoo-bin','shell','-c',target['config'],'-d',target['database'],'--db-filter=^'+target['database']+'$','--no-http','--workers=0','--max-cron-threads=0','--log-level=error'],input=(here/source).read_text(),text=True,capture_output=True,check=True)
marker = 'STUDIO_AUDIT_OK' if args.studio else 'APP_AUDIT_OK'
assert marker in result.stdout, 'Audit incomplete; inspect the private server log'
print(result.stdout)
