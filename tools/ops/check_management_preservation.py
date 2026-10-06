"""Read-only comparison of live management rows against the tested baseline."""
import argparse
import json
from pathlib import Path
import re
from manage_management import snapshot

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('environment',choices=('development','cerro'))
p.add_argument('run_id')
args=p.parse_args()
assert re.fullmatch('[a-z0-9_]{1,24}',args.run_id)
here=Path(__file__).parent
registry=json.loads((here/'environments.json').read_text())
database=registry['environments'][args.environment]['database']
stage=Path('/opt/steps-validation')/('management_'+args.environment+'_'+args.run_id)
before=json.loads((stage/'business_before.json').read_text())
assert snapshot(database)==before,'Management rows or amounts differ from the tested baseline'
print('MANAGEMENT_BUSINESS_PRESERVED database='+database+' tables='+str(len(before)))
