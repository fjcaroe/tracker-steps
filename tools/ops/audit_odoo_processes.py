"""Report Odoo process scopes; never print credentials or complete command lines."""
import json
from pathlib import Path

keys = {'-c': 'config', '--config': 'config', '-d': 'database', '--database': 'database',
        '--http-port': 'http_port', '--xmlrpc-port': 'http_port', '--db-filter': 'dbfilter',
        '--workers': 'workers', '--max-cron-threads': 'cron_threads', '--http-interface': 'interface'}
for path in Path('/proc').glob('[0-9]*/cmdline'):
    try:
        argv = path.read_bytes().decode(errors='replace').split('\0')
        if not any(Path(arg).name == 'odoo-bin' for arg in argv):
            continue
        row = {'pid': int(path.parent.name), 'scope': (path.parent/'cgroup').read_text().strip()}
        for index, arg in enumerate(argv):
            key, sep, value = arg.partition('=')
            if key in keys:
                row[keys[key]] = value if sep else argv[index + 1]
            elif arg in ('--stop-after-init', '--no-http', '--test-enable'):
                row[arg[2:].replace('-', '_')] = True
        print(json.dumps(row))
    except (OSError, IndexError):
        continue
