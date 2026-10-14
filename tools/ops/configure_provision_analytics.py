"""Test an explicitly identified native analytical relation, then apply with backup."""
import argparse
import configparser
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

HERE = Path(__file__).resolve().parent
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('phase', choices=('test', 'apply'))
p.add_argument('environment', choices=('development', 'cerro'))
p.add_argument('--dimension', choices=('season', 'shipment'), required=True)
p.add_argument('--master-id', type=int, required=True)
p.add_argument('--account-id', type=int, required=True)
p.add_argument('--journal-id', type=int, default=0, help='Existing configured provision journal; correct only documents whose current journal has no default account')
p.add_argument('--qa-database', required=True)
p.add_argument('--proof', type=Path, required=True)
a = p.parse_args()
assert os.geteuid() == 0 and a.master_id > 0 and a.account_id > 0
assert re.fullmatch('MANAGEMENT_QA_[A-Za-z0-9_]+', a.qa_database)
t = json.loads((HERE / 'environments.json').read_text())['environments'][a.environment]
assert a.qa_database.startswith('MANAGEMENT_QA_' + ('DEVELOPMENT' if a.environment == 'development' else 'CERRO') + '_')
cfg = configparser.ConfigParser(interpolation=None)
cfg.read(t['config'])
opts = cfg['options']
assert opts['db_name'] == t['database'] and int(opts['http_port']) == t['port']
user = subprocess.check_output(['systemctl', 'show', '--value', '--property=User', t['service']], text=True).strip()
script = (HERE / 'probe_provision_analytics.py').read_text()
spec = {'environment': a.environment, 'dimension': a.dimension, 'master_id': a.master_id,
        'account_id': a.account_id, 'qa_database': a.qa_database,
        'journal_id': a.journal_id,
        'script_sha256': hashlib.sha256(script.encode()).hexdigest()}
with open('/run/lock/steps-environments.lock', 'a') as lock:
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    for cmd in Path('/proc').glob('[0-9]*/cmdline'):
        try:
            argv = cmd.read_bytes().decode(errors='replace').split('\0')
        except OSError:
            continue
        if any(Path(arg).name == 'odoo-bin' for arg in argv):
            assert not any(arg in ('-u', '-i', '--update', '--init') or arg.startswith(('--update=', '--init=')) for arg in argv), 'Concurrent upgrade'
    backup = None
    if a.phase == 'apply':
        tested = json.loads(a.proof.read_text())
        assert tested['spec'] == spec and tested['tested'] and tested['costing_checked']
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        backup = Path('/opt/steps_backups') / ('provision_analytics_' + a.environment + '_' + stamp)
        backup.mkdir(mode=0o700)
        shutil.copy2(t['config'], backup / 'odoo.conf')
        with (backup / 'database.dump').open('wb') as out:
            subprocess.run(['sudo', '-u', 'postgres', 'pg_dump', '-Fc', t['database']], stdout=out, check=True)
        store = Path(opts['data_dir']) / 'filestore' / t['database']
        if store.exists():
            subprocess.run(['rsync', '-a', str(store) + '/', str(backup / 'filestore') + '/'], check=True)
        (backup / 'requested_relation.json').write_text(json.dumps(spec))
    database = a.qa_database if a.phase == 'test' else t['database']
    params = dict(spec, apply=a.phase == 'apply', source_sha256=None if a.phase == 'test' else tested['source_sha256'])
    result = subprocess.run(['sudo', '-u', user, '/usr/bin/python3.10', '/opt/odoo18/odoo-bin',
        'shell', '-c', t['config'], '-d', database, '--db-filter=^' + database + '$',
        '--no-http', '--workers=0', '--max-cron-threads=0', '--log-level=error'],
        input='PARAMS=' + repr(params) + '\n' + script, text=True, capture_output=True)
    output = a.proof.with_suffix('.' + a.phase + '.log')
    output.write_text(result.stdout + result.stderr)
    rows = [line for line in result.stdout.splitlines() if line.startswith('PROVISION_ANALYTICS_OK ')]
    assert result.returncode == 0 and len(rows) == 1, 'Probe failed; inspect ' + str(output)
    proof = json.loads(rows[0].split(' ', 1)[1])
    proof.update(spec=spec, backup=str(backup) if backup else None)
    destination = a.proof if a.phase == 'test' else a.proof.with_suffix('.applied.json')
    destination.write_text(json.dumps(proof, indent=2))
    print('PROVISION_ANALYTICS_' + a.phase.upper() + '_OK ' + json.dumps(proof))
