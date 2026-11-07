"""Finish a greenhouse post-start check without repeating the installation."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import re
import subprocess
import time
import urllib.error
import urllib.request

from manage_ecoplantas_greenhouse import (
    ROOT, DB, USER, CONF, SERVICE, baseline, configure, credentials, deliveries,
    installed, preserve, private_json, query, snapshot,
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run_id')
    parser.add_argument('backup', type=Path)
    args = parser.parse_args()
    assert os.geteuid() == 0 and re.fullmatch('[a-z0-9_]{1,16}', args.run_id)
    backup = args.backup.resolve()
    assert backup.parent == ROOT and re.fullmatch(r'greenhouse-backup-\d{8}T\d{6}Z', backup.name)
    assert (backup / 'database.dump').is_file()
    # Recheck a completed native install; never run an upgrade or repair writes.
    assert 'GREENHOUSE_SCENARIO_OK ' in (backup / 'configure.log').read_text()
    stage = Path('/opt/steps-validation/ecoplantas-greenhouse_' + args.run_id)
    proof = json.loads((stage / 'qa-passed.json').read_text())
    access = json.loads((ROOT / 'review-access-verified.json').read_text())
    assert proof['user_id'] == access['live']['user_id'] and proof['flow']['traceable_input_output']
    with open('/run/lock/steps-environments.lock', 'a') as lease:
        print('ECOPLANTAS_GREENHOUSE_VERIFY_WAITING_LEASE', flush=True)
        fcntl.flock(lease, fcntl.LOCK_EX)
        current = baseline()
        expected = dict(proof['baseline'])
        current.pop('installed'); expected.pop('installed')
        assert current == expected, 'The tested code, configuration or native sources changed'
        assert installed(DB) == proof['versions']
        subprocess.run(['systemctl', 'is-active', '--quiet', SERVICE], check=True)
        for attempt in range(12):
            try:
                with urllib.request.urlopen('https://ecoplantas.stepsapp.cl/web/login?db=ECOPLANTAS', timeout=10) as response:
                    assert response.status == 200 and b'password' in response.read()
                break
            except (urllib.error.URLError, TimeoutError):
                if attempt == 11:
                    raise
                time.sleep(5)
        # Restore the pre-install backup privately to compare every existing
        # business row and encrypted credential. No application can use this DB.
        before_db = 'ECOPLANTAS_GH_BEFORE_' + args.run_id
        assert not query('postgres', "SELECT 1 FROM pg_database WHERE datname='" + before_db + "'")
        subprocess.run(['sudo', '-u', 'postgres', 'createdb', '-O', USER, before_db], check=True)
        try:
            query(before_db, 'CREATE EXTENSION IF NOT EXISTS pg_trgm; CREATE EXTENSION IF NOT EXISTS unaccent;')
            with (backup / 'database.dump').open('rb') as stream:
                subprocess.run(['sudo', '-u', 'postgres', 'pg_restore', '--no-owner', '--no-acl',
                    '--no-comments', '--role', USER, '-d', before_db], stdin=stream, check=True)
            before = snapshot(before_db)
            preserve(DB, before, credentials(before_db), deliveries(before_db))
            active = [int(value) for value in query(DB, 'SELECT id FROM ir_cron WHERE active ORDER BY id').splitlines()]
            native = configure(DB, CONF, stage, proof['user_id'], active)
            preserve(DB, before, credentials(before_db), deliveries(before_db))
        finally:
            subprocess.run(['sudo', '-u', 'postgres', 'dropdb', before_db], check=True)
        native.update(backup=str(backup), credentials_preserved=True,
            existing_business_preserved=True, post_start_recheck=True)
        private_json(stage / 'deployed.json', native)
        print('ECOPLANTAS_GREENHOUSE_DEPLOYED ' + json.dumps(native), flush=True)


if __name__ == '__main__':
    main()
