"""Read the latest isolated integration test log, never a live service log."""
import argparse
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('environment', choices=['development', 'demo'])
args = parser.parse_args()
logs = sorted((Path('/opt/steps-agro-qa') / args.environment).glob('tests-*.log'))
if not logs:
    raise SystemExit('No isolated integration test log found')
path = logs[-1]
lines = path.read_text(errors='replace').splitlines()
print(path)
for index, line in enumerate(lines):
    if 'ERROR' in line or 'FAIL' in line or 'Traceback' in line or 'failed, ' in line:
        print('\n'.join(lines[index:min(len(lines), index + 30)]))
print('\n'.join(lines[-12:]))
