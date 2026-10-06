"""Read PostgreSQL usage and Odoo pool sizes without credentials or query text."""
import configparser
import json
from pathlib import Path
from canonical_ports import query

registry = json.loads((Path(__file__).parent / 'environments.json').read_text())
rows = []
for name, target in registry['environments'].items():
    cfg = configparser.ConfigParser(interpolation=None)
    cfg.read(target['config'])
    options = cfg['options']
    rows.append({'environment': name, 'role': target['role'],
                 **{k: options.get(k) for k in ('db_name', 'dbfilter', 'db_maxconn', 'workers', 'max_cron_threads')}})
print(json.dumps({'limit': int(query('postgres', 'SHOW max_connections')),
                  'used': int(query('postgres', 'SELECT count(*) FROM pg_stat_activity')),
                  'connections': json.loads(query('postgres', "SELECT json_agg(t) FROM (SELECT datname,state,count(*) FROM pg_stat_activity GROUP BY datname,state ORDER BY count(*) DESC) t")),
                  'services': rows}))
