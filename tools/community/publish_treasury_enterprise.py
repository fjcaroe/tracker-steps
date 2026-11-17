"""T223: publish the certified Treasury core while retaining Cerro's Enterprise reports."""
import argparse
import ast
import configparser
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import pwd
import re
import shutil
import subprocess
import sys
import time
from urllib.request import urlopen

from manage_community_reports import TARGETS, digest, runtime_contract, run, sql, tree
from validate_community_reports import action_contract
from validate_treasury_extraction import field_ids, report_menus, same_values, security_contract, snapshot


MODULES = ('step_accounting_multicurrency_core', 'step_accounting_multicurrency',
           'step_account_treasury', 'step_account_treasury_reports')
DATABASE = 'CERRO_EL_PLOMO'
CONFIG = Path('/etc/odoo18-cerroelplomo.conf')
SERVICE = 'odoo18-cerroelplomo.service'
USER = 'cerro_odoo18'
URL = 'https://cerroelplomo.stepsapp.cl'
INSTALL = ('step_accounting_multicurrency_core', 'step_account_treasury_reports')
UPGRADE = ('step_accounting_multicurrency', 'step_account_treasury')
HERE = Path(__file__).resolve().parent


def package_files(source):
    return {module + '/' + name: sha for module in MODULES
            for name, sha in tree(source / module).items()}


def verify_development(source, version):
    development = runtime_contract(TARGETS['development'][1], UPGRADE + INSTALL[:1])
    for module, reference in development['sources'].items():
        assert development['installed_versions'][module] == version[module], module
        assert reference['files'] == tree(source / module), module
    assert set(development['sources']) == set(UPGRADE + INSTALL[:1])


def business_contract(database):
    return {'menus': report_menus(database), 'actions': action_contract(database),
            'fields': field_ids(database), 'security': security_contract(database)}


def verify_flow(command, evidence):
    probe = (HERE / 'verify_treasury_enterprise.py').read_text()
    result = run(*command, input=probe, text=True, capture_output=True)
    evidence.write_text(result.stdout + result.stderr)
    assert 'T223_ENTERPRISE_FLOW_OK' in result.stdout
    print(result.stdout.strip(), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=('capture', 'verify-copy', 'deploy'))
    parser.add_argument('root', type=Path)
    args = parser.parse_args()
    assert os.geteuid() == 0
    root = args.root.resolve()
    assert root.parent == Path('/opt/steps-validation') and root.name.startswith('t223-enterprise-')
    baseline = root / 'cerro-source.json'
    source = root / 'addons'
    proof = root / 'cerro-copy'
    if args.operation == 'capture':
        assert not baseline.exists()
        baseline.write_text(json.dumps(runtime_contract(CONFIG, MODULES), indent=2))
        baseline.chmod(0o600)
        return

    passed = json.loads((proof / 'passed.json').read_text())
    copy = passed['database']
    assert re.fullmatch(r'MANAGEMENT_QA_CERRO_TREASURY_T223[A-Z0-9_]+', copy)
    assert passed['mode'] == 'cerro-copy' and passed['business_preserved'] and not passed['writes_to_production']
    expected = json.loads((proof / 'source-files.json').read_text())
    assert package_files(source) == expected
    assert re.search(r'0 failed, 0 error\(s\) of [1-9]\d* tests', Path(passed['tests_log']).read_text())
    versions = {module: ast.literal_eval((source / module / '__manifest__.py').read_text())['version']
                for module in MODULES}
    verify_development(source, versions)

    config = configparser.ConfigParser(interpolation=None)
    config.read(CONFIG)
    opts = config['options']
    assert opts['db_name'] == DATABASE
    base = ['sudo', '-u', USER, '/usr/bin/python3.10']
    common = ['-c', str(CONFIG), '--no-http', '--workers=0', '--max-cron-threads=0', '--load=base,web']
    copy_log = proof / 'enterprise-flow.log'
    if args.operation == 'verify-copy':
        before = snapshot(copy)
        command = base + ['/opt/odoo18/odoo-bin', 'shell', '-d', copy, '--db-filter=^' + copy + '$',
                          '--addons-path=' + str(source) + ',' + opts['addons_path'],
                          '--data-dir=' + str(proof / 'data'), '--log-level=critical'] + common
        verify_flow(command, copy_log)
        assert same_values(before, snapshot(copy))
        return

    assert 'T223_ENTERPRISE_FLOW_OK' in copy_log.read_text()
    with open('/run/lock/steps-environments.lock', 'a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        contract = runtime_contract(CONFIG, MODULES)
        assert contract == json.loads(baseline.read_text()), 'Concurrent change; take another fresh copy'
        assert sql(DATABASE, "SELECT count(*) FROM ir_module_module WHERE state IN ('to install','to upgrade','to remove')") == '0'
        installed = contract['installed_versions']
        assert all(module in installed for module in UPGRADE)
        assert not any(module in installed for module in INSTALL + ('step_treasury_community_reports',))
        assert all(tuple(map(int, versions[m].split('.'))) >= tuple(map(int, installed[m].split('.'))) for m in UPGRADE)
        root_release = Path('/opt/steps-managed/treasury/cerro') / 't223-82a3e8f'
        stage = Path('/opt/steps_backups') / ('treasury_cerro_t223_' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
        overlay = root_release / 'addons'
        overlay.mkdir(parents=True)
        stage.mkdir(mode=0o700)
        identity = pwd.getpwnam(USER)
        for module in MODULES:
            shutil.copytree(source / module, overlay / module, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        for item in (root_release, *root_release.rglob('*')):
            os.chown(item, identity.pw_uid, identity.pw_gid)
        assert package_files(overlay) == expected

        shutil.copy2(CONFIG, stage / 'odoo.conf')
        run('systemctl', 'stop', SERVICE)
        try:
            assert runtime_contract(CONFIG, MODULES) == contract
            before = snapshot(DATABASE)
            metadata = business_contract(DATABASE)
            assert len(metadata['menus']) == len(metadata['actions']['native_five']) == 5
            dump = stage / 'database.dump'
            with dump.open('wb') as stream:
                run('sudo', '-u', 'postgres', 'pg_dump', '-Fc', DATABASE, stdout=stream)
            run('pg_restore', '-l', str(dump), stdout=subprocess.DEVNULL)
            store = Path(opts['data_dir']) / 'filestore' / DATABASE
            if store.is_dir():
                run('rsync', '-a', str(store) + '/', str(stage / 'filestore') + '/')
            (stage / 'business-before.json').write_text(json.dumps(before))
            (stage / 'metadata-before.json').write_text(json.dumps(metadata))
            revised, count = re.subn(r'(?m)^\s*addons_path\s*=.*$',
                                     'addons_path = ' + str(overlay) + ',' + opts['addons_path'], CONFIG.read_text())
            assert count == 1
            CONFIG.write_text(revised)
            log = stage / 'upgrade.log'
            with log.open('wb') as output:
                run(*(base + [str(source / 'tools/ops/run_sag_cerro_upgrade.py')] + common + [
                    '-d', DATABASE, '-i', ','.join(INSTALL), '-u', ','.join(UPGRADE), '--stop-after-init']),
                    stdout=output, stderr=subprocess.STDOUT)
            sys.path.insert(0, str(HERE.parent / 'ops'))
            from manage_management import errors
            diagnostics = log.read_text(errors='replace')
            assert 'Modules loaded.' in diagnostics and not errors(diagnostics)
            assert same_values(before, snapshot(DATABASE))
            assert business_contract(DATABASE) == metadata
            effective = runtime_contract(CONFIG, MODULES)
            for module in MODULES:
                assert effective['installed_versions'][module] == versions[module]
                assert effective['sources'][module]['files'] == tree(source / module)
            assert 'step_treasury_community_reports' not in effective['installed_versions']
        finally:
            run('systemctl', 'start', SERVICE)
        run('systemctl', 'is-active', '--quiet', SERVICE)
        for attempt in range(20):
            try:
                with urlopen(URL + '/web/login', timeout=15) as response:
                    assert response.status == 200 and b'password' in response.read()
                break
            except (OSError, AssertionError):
                if attempt == 19:
                    raise
                time.sleep(2)
        verify_flow(base + ['/opt/odoo18/odoo-bin', 'shell', '-d', DATABASE, '--log-level=critical'] + common,
                    stage / 'verify.log')
        (stage / 'published.json').write_text(json.dumps({'versions': versions, 'validation': str(proof),
                                                          'files': expected, 'business_preserved': True}))
        print('T223_ENTERPRISE_DEPLOY_OK ' + str(stage), flush=True)


if __name__ == '__main__':
    main()
