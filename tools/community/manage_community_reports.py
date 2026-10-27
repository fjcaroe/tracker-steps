"""Publish the proven Community reports only to Development or customer QA.

No production target, database refresh, Enterprise removal or credential writes.
Requires fresh target-clone proof, identical addon files, unchanged source,
shared lease, no downgrade, and full recovery backups before service changes.
"""
import argparse
from datetime import datetime, timezone
import ast
import configparser
import fcntl
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import shutil
import subprocess
import sys
import urllib.request

MODULES = ('step_accounting_multicurrency_core', 'step_accounting_multicurrency',
           'step_account_treasury', 'step_account_treasury_reports', 'step_treasury_community_reports')
TARGETS = {
    'development': ('LAB_TAREAS', '/etc/dev_odoo18.conf', 'odoo18-dev.service', 'odoo', 'https://desarrollo.stepsapp.cl'),
    'qa-cerro': ('QA-CERROELPLOMO', '/etc/odoo18-qa-cerroelplomo.conf', 'odoo18-qa-cerroelplomo.service', 'cerroqa_odoo18', 'https://qa-cerroelplomo.stepsapp.cl'),
}


def run(*command, **kwargs):
    return subprocess.run(command, check=True, **kwargs)


def sql(database, statement):
    return run('sudo', '-u', 'postgres', 'psql', '-q', '-v', 'ON_ERROR_STOP=1', '-d', database,
               '-At', input=statement, text=True, capture_output=True).stdout.strip()


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tree(path):
    return {str(p.relative_to(path)): digest(p) for p in sorted(path.rglob('*'))
            if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc'}


def runtime_contract(conf):
    config = configparser.ConfigParser(interpolation=None); config.read(conf)
    opts = config['options']
    versions = json.loads(sql(opts['db_name'], "SELECT coalesce(json_object_agg(name,latest_version),'{}'::json) "
        "FROM ir_module_module WHERE state='installed'"))
    roots = [Path(p.strip()) for p in opts['addons_path'].split(',')]
    sources = {}
    for name in MODULES:
        source = next((root / name for root in roots if (root / name / '__manifest__.py').exists()), None)
        if name in versions:
            assert source, 'Missing installed module source: ' + name
            sources[name] = {'path': str(source), 'files': tree(source)}
    return {'config_sha256': digest(Path(conf)), 'installed_versions': versions, 'sources': sources}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--environment', choices=TARGETS, required=True)
    parser.add_argument('--proof-root', type=Path, required=True)
    parser.add_argument('--community-root', type=Path, required=True)
    parser.add_argument('--cerro-root', type=Path, required=True)
    parser.add_argument('--development-release', type=Path)
    args = parser.parse_args()
    assert os.geteuid() == 0
    database, conf, service, user, url = TARGETS[args.environment]
    conf = Path(conf)
    proof = args.proof_root.resolve() / 'cerro-copy'
    for root, mode in ((args.proof_root, 'cerro-copy'), (args.community_root, 'community'), (args.cerro_root, 'cerro-copy')):
        passed = json.loads((root / mode / 'passed.json').read_text())
        assert passed['writes_to_production'] is False
        assert (root / mode / 'source-files.json').read_bytes() == (proof / 'source-files.json').read_bytes(), 'Package files differ'
    source = args.proof_root.resolve() / 'addons'
    expected_files = json.loads((proof / 'source-files.json').read_text())
    actual = {str(p.relative_to(source)): digest(p) for module in MODULES for p in (source / module).rglob('*')
              if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc'}
    assert actual == expected_files
    if args.environment == 'qa-cerro':
        assert args.development_release, 'First review this package in Desarrollo'
        development = json.loads((args.development_release / 'deployed.json').read_text())
        assert development['source_files'] == actual and development['business_preserved']
    contract = json.loads((proof / 'source-contract.json').read_text())
    before = json.loads((proof / 'business-before.json').read_text())
    package_hash = hashlib.sha256(json.dumps(actual, sort_keys=True).encode()).hexdigest()
    stage = Path('/opt/steps-community/releases') / args.environment / (package_hash + '-' + datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S'))
    assert not stage.exists(), 'Release path already exists; do not overwrite'
    stage.mkdir(parents=True, mode=0o750)
    config = configparser.ConfigParser(interpolation=None); config.read(conf); opts = config['options']
    assert opts['db_name'] == database
    from validate_community_reports import snapshot, same_values, field_ids, security_contract, report_menus, action_contract
    with open('/run/lock/steps-environments.lock', 'a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        assert runtime_contract(conf) == contract, 'Concurrent configuration, source or version change'
        assert sql(database, "SELECT count(*) FROM ir_module_module WHERE state IN ('to install','to upgrade','to remove')") == '0', 'Another module operation is pending'
        installed = contract['installed_versions']
        for name in MODULES:
            version = ast.literal_eval((source / name / '__manifest__.py').read_text())['version']
            if name in installed:
                assert tuple(map(int, version.split('.'))) >= tuple(map(int, installed[name].split('.'))), 'Downgrade: ' + name
        overlay = stage / 'addons'; overlay.mkdir()
        for name in MODULES:
            shutil.copytree(source / name, overlay / name, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        identity = pwd.getpwnam(user)
        for p in [stage, *stage.rglob('*')]: os.chown(p, identity.pw_uid, identity.pw_gid)
        assert {str(p.relative_to(overlay)): digest(p) for module in MODULES for p in (overlay / module).rglob('*') if p.is_file()} == expected_files
        run('systemctl', 'stop', service)
        try:
            assert runtime_contract(conf) == contract, 'Concurrent change before service stop'
            assert same_values(before, snapshot(database)), 'Business data changed since fresh copy; validate a new copy'
            old_actions = action_contract(database)
            old_fields = field_ids(database); old_security = security_contract(database); old_menus = report_menus(database)
            shutil.copy2(conf, stage / 'config-before.conf'); (stage / 'config-before.conf').chmod(0o600)
            with (stage / 'recovery.dump').open('wb') as stream:
                run('sudo', '-u', 'postgres', 'pg_dump', '-Fc', database, stdout=stream)
            store = Path(opts['data_dir']) / 'filestore' / database
            run('rsync', '-a', str(store) + '/', str(stage / 'filestore-backup') + '/')
            text, count = re.subn(r'(?m)^\s*addons_path\s*=.*$', 'addons_path = ' + str(overlay) + ',' + opts['addons_path'], conf.read_text())
            assert count == 1
            conf.write_text(text)
            init = [m for m in ('step_accounting_multicurrency_core', 'step_treasury_community_reports') if m not in installed]
            update = [m for m in MODULES if m in installed]
            base = ['sudo', '-u', user, '/usr/bin/python3.10', str(source / 'tools/ops/run_sag_cerro_upgrade.py')]
            options = ['-c', str(conf), '-d', database, '--no-http', '--workers=0', '--max-cron-threads=0', '--load=base,web']
            commands = (['-i', ','.join(init)] if init else []) + (['-u', ','.join(update)] if update else [])
            log = stage / 'upgrade.log'
            with (stage / 'bootstrap.log').open('w') as stream:
                result = subprocess.run(base + options + commands + ['--stop-after-init', '--logfile=' + str(log)], stdout=stream, stderr=subprocess.STDOUT)
            diagnostics = log.read_text(errors='replace')
            sys.path.insert(0, str(source / 'tools/ops'))
            from manage_management import errors as module_errors
            allowed_missing = tuple(name for name in ('steps_api',) if name in installed)
            assert result.returncode == 0 and 'Modules loaded.' in diagnostics and not module_errors(diagnostics, allowed_missing), 'Upgrade failed; preserve recovery directory'
            assert same_values(before, snapshot(database)), 'Business values changed'
            assert action_contract(database) == old_actions, 'Existing client actions changed'
            assert field_ids(database) == old_fields and security_contract(database) == old_security
            after_menus = report_menus(database)
            strip = lambda menus: {k:{f:v for f,v in row.items() if f not in ('action','write_date','write_uid')} for k,row in menus.items()}
            assert strip(old_menus) == strip(after_menus)
            probe = (source / 'tools/community/verify_community_reports.py').read_text()
            result = run(*(base + ['shell'] + options + ['--log-level=critical']), input="MODE='" + args.environment + "'\n" + probe, text=True, capture_output=True)
            (stage / 'verify.log').write_text(result.stdout + result.stderr)
            assert 'COMMUNITY_REPORTS_NATIVE_FLOW_OK' in result.stdout and 'COMMUNITY_TREASURY_REGISTRY_OK' in result.stdout
            assert same_values(before, snapshot(database))
            confirmed_versions = {}
            for name in init + update:
                version = ast.literal_eval((overlay / name / '__manifest__.py').read_text())['version']
                actual_version = sql(database, "SELECT latest_version FROM ir_module_module WHERE name='" + name + "' AND state='installed'")
                assert actual_version == version, 'Installed version differs: ' + name
                confirmed_versions[name] = actual_version
            if args.environment == 'qa-cerro':
                assert sql(database, "SELECT value FROM ir_config_parameter WHERE key='database.is_neutralized'") == 'true'
                assert sql(database, 'SELECT count(*) FROM ir_cron WHERE active') == '0'
                assert sql(database, "SELECT count(*) FROM ir_mail_server WHERE active AND smtp_host!='invalid'") == '0'
            (stage / 'deployed.json').write_text(json.dumps({'package_hash': package_hash, 'url': url, 'source_files': actual,
                'installed_versions': confirmed_versions, 'business_preserved': True}, indent=2))
        finally:
            # Retain upgraded state and recovery dump; never discard new user data.
            run('systemctl', 'start', service)
        run('systemctl', 'is-active', '--quiet', service)
        with urllib.request.urlopen(url + '/web/login', timeout=30) as response:
            assert response.status == 200
        print('COMMUNITY_REPORTS_DEPLOYED ' + json.dumps({'environment': args.environment, 'url': url, 'evidence': str(stage)}))


if __name__ == '__main__': main()
