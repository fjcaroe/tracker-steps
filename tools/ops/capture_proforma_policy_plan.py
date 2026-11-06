"""Capture the explicitly reported Cerro draft to a private plan (read-only)."""
import argparse
import json
from pathlib import Path
import subprocess


p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--order', type=int, required=True)
p.add_argument('--output', type=Path, required=True)
args = p.parse_args()
here = Path(__file__).resolve().parent
target = json.loads((here/'environments.json').read_text())['environments']['cerro']
user = subprocess.check_output(['systemctl', 'show', '--value', '--property=User', target['service']], text=True).strip()
script = ('import sys,json\nsys.path.insert(0,' + repr(str(here)) + ')\n'
          'from proforma_policy_case import capture\n'
          'print("PROFORMA_POLICY_PLAN " + json.dumps(capture(env,' + str(args.order) + ')))\n'
          'env.cr.rollback()\n')
result = subprocess.run(['sudo', '-u', user, '/usr/bin/python3.10', '/opt/odoo18/odoo-bin',
    'shell', '-c', target['config'], '-d', target['database'], '--no-http', '--workers=0',
    '--max-cron-threads=0', '--log-level=error'], input=script, text=True, capture_output=True)
assert result.returncode == 0, result.stderr[-1500:]
row = next(line.split(' ', 1)[1] for line in result.stdout.splitlines() if line.startswith('PROFORMA_POLICY_PLAN '))
args.output.write_text(row)
args.output.chmod(0o600)
print('PROFORMA_POLICY_PLAN_CAPTURED')
