"""Stop only an Odoo process whose -d argument is our disposable clone."""
import argparse
from pathlib import Path
import re
import os
import signal

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('environment', choices=('development', 'demo', 'cerro'))
parser.add_argument('run_id')
args = parser.parse_args()
assert re.fullmatch('[a-z0-9_]{1,24}', args.run_id)
database = 'MANAGEMENT_QA_' + args.environment.upper() + '_' + args.run_id
for command in Path('/proc').glob('[0-9]*/cmdline'):
    try:
        argv = command.read_bytes().decode().split('\x00')
    except (OSError, UnicodeError):
        continue
    if any(Path(arg).name == 'odoo-bin' for arg in argv):
        for index, arg in enumerate(argv[:-1]):
            if arg == '-d' and argv[index + 1] == database:
                os.kill(int(command.parent.name), signal.SIGTERM)
                print('CLONE_STOP_REQUESTED pid=' + command.parent.name + ' database=' + database)
