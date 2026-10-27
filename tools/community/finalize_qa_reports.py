"""Complete a verified QA release interrupted only by its neutrality gate.

Does not reinstall modules or restore a database. Requires all original proofs,
backups, unchanged business rows, versions, IDs and actions; restores QA cron
neutrality under the shared lease, verifies native flows, then starts the service.
"""
import argparse
import ast
import configparser
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
import urllib.request

from manage_community_reports import MODULES, TARGETS, digest, run, sql
from validate_community_reports import snapshot, same_values, field_ids, security_contract, report_menus, action_contract


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--release', type=Path, required=True)
    parser.add_argument('--proof-root', type=Path, required=True)
    args = parser.parse_args()
    assert os.geteuid() == 0
    database, conf, service, user, url = TARGETS['qa-cerro']
    release = args.release.resolve(); proof = args.proof_root.resolve() / 'cerro-copy'
    assert release.parent == Path('/opt/steps-community/releases/qa-cerro')
    assert (release / 'recovery.dump').stat().st_size > 0 and (release / 'config-before.conf').exists()
    assert not (release / 'deployed.json').exists(), 'Never overwrite completed delivery evidence'
    passed = json.loads((proof / 'passed.json').read_text()); assert passed['business_preserved']
    expected = json.loads((proof / 'source-files.json').read_text())
    actual = {str(p.relative_to(release / 'addons')): digest(p) for m in MODULES for p in (release / 'addons' / m).rglob('*')
              if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc'}
    assert actual == expected
    package_hash = hashlib.sha256(json.dumps(actual, sort_keys=True).encode()).hexdigest()
    assert release.name.startswith(package_hash + '-')
    config = configparser.ConfigParser(interpolation=None); config.read(conf)
    assert config['options']['db_name'] == database and config['options'].get('max_cron_threads') == '0'
    assert config['options']['addons_path'].split(',')[0].strip() == str(release / 'addons')
    # Confirm the original backup was neutral: don't reinterpret an intentional
    # task configuration as permission to turn tasks on or change their code.
    with (release / 'recovery.dump').open('rb') as stream:
        dump = run('sudo', '-u', 'postgres', 'pg_restore', '--data-only', '--table=ir_cron', '--file=-', stdin=stream, capture_output=True).stdout.decode()
    match = re.search(r'COPY public.ir_cron \(([^)]+)\) FROM stdin;\n(.*?)\n\\\.', dump, re.S)
    assert match
    columns = [c.strip() for c in match.group(1).split(',')]
    assert all(row.split('\t')[columns.index('active')] == 'f' for row in match.group(2).splitlines())
    before = json.loads((release / 'business-before.json').read_text())
    assert same_values(before, json.loads((release / 'business-after.json').read_text()))
    with open('/run/lock/steps-environments.lock', 'a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        run('systemctl', 'stop', service)
        try:
            assert same_values(before, snapshot(database)), 'Live data changed; do not overwrite exercises'
            assert field_ids(database) == json.loads((proof / 'field-ids-before.json').read_text())
            assert security_contract(database) == json.loads((proof / 'security-before.json').read_text())
            assert action_contract(database) == json.loads((proof / 'actions-before.json').read_text())
            strip = lambda menus: {k:{f:v for f,v in row.items() if f not in ('action','write_date','write_uid')} for k,row in menus.items()}
            assert strip(report_menus(database)) == strip(json.loads((proof / 'menus-before.json').read_text()))
            assert sql(database, "SELECT count(*) FROM ir_module_module WHERE state IN ('to install','to upgrade','to remove')") == '0'
            versions = {}
            for name in MODULES:
                current = sql(database, "SELECT latest_version FROM ir_module_module WHERE name='" + name + "' AND state='installed'")
                if current:
                    assert current == ast.literal_eval((release / 'addons' / name / '__manifest__.py').read_text())['version']
                    versions[name] = current
            assert 'step_treasury_community_reports' in versions
            active = int(sql(database, 'SELECT count(*) FROM ir_cron WHERE active'))
            sql(database, 'UPDATE ir_cron SET active=false WHERE active; UPDATE ir_mail_server SET active=false WHERE active; UPDATE fetchmail_server SET active=false WHERE active;')
            assert sql(database, 'SELECT count(*) FROM ir_cron WHERE active') == '0'
            assert sql(database, 'SELECT count(*) FROM ir_mail_server WHERE active') == '0'
            assert sql(database, 'SELECT count(*) FROM fetchmail_server WHERE active') == '0'
            assert sql(database, "SELECT value FROM ir_config_parameter WHERE key='database.is_neutralized'") == 'true'
            probe = (Path(__file__).parent / 'verify_community_reports.py').read_text()
            result = run('sudo', '-u', user, '/usr/bin/python3.10', '/opt/odoo18/odoo-bin', 'shell', '-c', conf, '-d', database,
                '--no-http', '--load=base,web', '--log-level=critical', input="MODE='qa-cerro'\n" + probe, capture_output=True, text=True)
            (release / 'neutralized-verify.log').write_text(result.stdout + result.stderr)
            assert 'COMMUNITY_REPORTS_NATIVE_FLOW_OK' in result.stdout and 'COMMUNITY_TREASURY_REGISTRY_OK' in result.stdout
            assert same_values(before, snapshot(database))
            (release / 'neutralization.json').write_text(json.dumps({'original_active_crons': 0, 'reactivated_definitions_disabled': active,
                'scheduler_threads': 0, 'mail_disabled': True, 'fetchmail_disabled': True, 'database_restored': False}))
            (release / 'deployed.json').write_text(json.dumps({'package_hash': package_hash, 'url': url, 'source_files': actual,
                'installed_versions': versions, 'business_preserved': True, 'neutrality_verified': True}, indent=2))
        finally:
            run('systemctl', 'start', service)
        for attempt in range(20):
            try:
                with urllib.request.urlopen(url + '/web/login', timeout=15) as response:
                    assert response.status == 200 and b'password' in response.read()
                break
            except (OSError, AssertionError):
                if attempt == 19: raise
                time.sleep(2)
        (release / 'http-passed.json').write_text(json.dumps({'url': url, 'status': 200, 'login': True}))
        print('COMMUNITY_REPORTS_QA_FINALIZED url=' + url + ' business_preserved=True neutralized=True')


if __name__ == '__main__': main()
