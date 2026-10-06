"""Read PostgreSQL usage and Odoo pool sizes without credentials or query text."""
import configparser
import json
import subprocess
from pathlib import Path
from canonical_ports import query

registry = json.loads((Path(__file__).parent / 'environments.json').read_text())
rows = []
for name, target in registry['environments'].items():
    cfg = configparser.ConfigParser(interpolation=None)
    cfg.read(target['config'])
    options = cfg['options']
    rows.append({'environment': name, 'role': target['role'],
                 'process': int(subprocess.check_output(['systemctl', 'show', '--property=MainPID', '--value', target['service']], text=True).strip()),
                 **{k: options.get(k) for k in ('db_name', 'dbfilter', 'db_maxconn', 'workers', 'max_cron_threads')}})
print(json.dumps({'limit': int(query('postgres', 'SHOW max_connections')),
                  'used': int(query('postgres', 'SELECT count(*) FROM pg_stat_activity')),
                  'connections': json.loads(query('postgres', "SELECT json_agg(t) FROM (SELECT datname,state,count(*) FROM pg_stat_activity GROUP BY datname,state ORDER BY count(*) DESC) t")),
                  'odoo_connections': json.loads(query('postgres', "SELECT json_agg(t) FROM (SELECT application_name,datname,count(*) FROM pg_stat_activity WHERE application_name ~ '^odoo-[0-9]+$' GROUP BY application_name,datname ORDER BY application_name,datname) t")),
                  'services': rows}))
