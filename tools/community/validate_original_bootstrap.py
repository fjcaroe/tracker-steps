"""Install a real no-demo/no-salary-seed Community profile in a new private DB.

The native mode delegates the unchanged exact-package Cerro reference runner.
Neither mode adopts original configuration or certifies Chilean payroll.
"""
import argparse
import configparser
import fcntl
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import subprocess
import sys

from accelerated_acceptance import HR_MODULES, prepare_hr_overlay
from build_original_bootstrap import verify_reproduction
from offline_process import offline_odoo
from validate_payroll_api import OFFICIAL_PIN, PIN
from validate_community_reports import sql


FINANCE = ('step_accounting_multicurrency_core', 'step_account_balance_analytic',
    'step_bank_export_core', 'step_account_treasury_batch', 'step_bank_security', 'step_accounting_multicurrency')
MODULES = ('step_payroll_contracts', 'step_payroll_oca_api', 'step_payroll_enterprise_reference',
    'step_simpledigital_oca_base', 'step_simpledigital_oca_security', 'l10n_cl_simpledigital_payroll') + HR_MODULES + FINANCE + (
    'step_l10n_cl_edi_core', 'step_l10n_cl_caf_custody_core', 'step_l10n_cl_caf_storage',
    'step_l10n_cl_caf_native_reference', 'step_batch_payment_grouping', 'step_batch_payment_core')
PROFILE = 'original-bootstrap-without-salary-seeds'
TAGS = '/step_payroll_oca_api:SavedInputValuesCase,/step_simpledigital_oca_base:ExistingDraftBatchCase'


def packet(source):
    return {str(path.relative_to(source)): hashlib.sha256(path.read_bytes()).hexdigest()
        for module in MODULES for path in sorted((source / module).rglob('*'))
        if path.is_file() and '__pycache__' not in path.parts}


def write(path, value):
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w') as stream:
        json.dump(value, stream, indent=2)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('community', 'cerro-reference'))
    for name in ('root', 'runtime', 'oca', 'provider-source'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--database', required=True)
    parser.add_argument('--tablespace', required=True)
    args = parser.parse_args()
    assert os.geteuid() == 0
    root = args.root.resolve()
    assert root.is_relative_to(Path('/opt/steps-validation'))
    source = root / 'addons'
    assert (root / 'original-bootstrap-derivation.json').is_file()
    assert (source / 'l10n_cl_simpledigital_payroll').resolve() == (root / 'profile-addons/l10n_cl_simpledigital_payroll').resolve()
    verify_reproduction(args.provider_source, root / 'profile-addons',
        dependency_roots=[source], community_root=args.runtime, oca_root=args.oca)
    if args.mode == 'cerro-reference':
        # The real unchanged native engine and source backup/lease/identity
        # checks remain in the already accepted runner. No cold provider is
        # installed over native Enterprise or copied from its source bodies.
        subprocess.run([sys.executable, str(source / 'tools/community/validate_payroll_api.py'), args.mode,
            '--profile', 'simpledigital', '--accelerated', '--custody-grouping', '--root', str(root),
            '--runtime', str(args.runtime), '--oca', str(args.oca), '--database', args.database,
            '--tablespace', args.tablespace], check=True)
        return
    assert re.fullmatch('COMMUNITY_PAYROLL_API_ORIGINAL_BOOTSTRAP_[A-Za-z0-9_]+', args.database)
    assert args.tablespace == 'steps_community_storage_20261028_community'
    assert all((source / name / '__manifest__.py').is_file() for name in MODULES)
    for runtime, expected in ((args.runtime, OFFICIAL_PIN), (args.oca, PIN)):
        git = ['git', '-c', 'safe.directory=' + str(runtime.resolve()), '-C', str(runtime)]
        assert subprocess.check_output(git + ['rev-parse', 'HEAD'], text=True).strip() == expected
        assert not subprocess.check_output(git + ['status', '--porcelain'], text=True).strip()
    stage = root / args.mode
    assert not stage.exists()
    stage.mkdir(mode=0o750)
    data, overlay = stage / 'data', stage / 'addons'
    data.mkdir(); overlay.mkdir()
    native_only = {'step_payroll_enterprise_reference', 'step_l10n_cl_caf_native_reference'}
    for name in MODULES:
        if name not in native_only:
            (overlay / name).symlink_to(source / name)
    for name in HR_MODULES + ('step_account_treasury_batch', 'step_bank_security', 'step_accounting_multicurrency'):
        (overlay / name).unlink()
    hr_overlay = prepare_hr_overlay(source, stage, overlay, community=True)
    for name in ('payroll', 'payroll_account'):
        (overlay / name).symlink_to(args.oca / name)
    frozen = packet(source)
    write(stage / 'source-files.json', frozen)
    write(stage / 'consumer-source-files.json', {str(path.relative_to(hr_overlay)): hashlib.sha256(path.read_bytes()).hexdigest()
        for name in HR_MODULES for path in sorted((hr_overlay / name).rglob('*'))
        if path.is_file() and '__pycache__' not in path.parts})
    identity = pwd.getpwnam('odoo')
    config = configparser.ConfigParser(interpolation=None)
    assert config.read('/etc/dev_odoo18.conf')
    database_user = config['options']['db_user']
    assert re.fullmatch('[a-z_][a-z0-9_]*', database_user)
    assert config['options']['db_name'] == 'LAB_TAREAS'
    with open('/run/lock/steps-environments.lock', 'a') as lease:
        print('COLD_BOOTSTRAP_WAITING_FOR_SHARED_LEASE', flush=True)
        fcntl.flock(lease, fcntl.LOCK_EX)
        assert not sql('postgres', "SELECT 1 FROM pg_database WHERE datname='" + args.database + "'")
        capacity = {}
        for name, path, reserve in (('postgres', Path(sql('postgres', 'SHOW data_directory')), 5 * 1024**3),
                                     ('artifacts', root, 2 * 1024**3)):
            state = os.statvfs(path)
            capacity[name] = state.f_bavail * state.f_frsize
            assert capacity[name] >= reserve, name + ' reserve below minimum'
        write(stage / 'storage-preflight.json', capacity)
        assert sql('postgres', "SELECT pg_tablespace_location(oid) FROM pg_tablespace WHERE spcname='" + args.tablespace + "'") == '/opt/steps-validation/community-payroll-storage-20261028/community'
        assert sql('postgres', "SELECT pg_get_userbyid(spcowner) FROM pg_tablespace WHERE spcname='" + args.tablespace + "'") == database_user
        subprocess.run(['sudo', '-u', 'postgres', 'createdb', '--owner=' + database_user, '--tablespace=' + args.tablespace, args.database], check=True)
        for path in (stage, *stage.rglob('*')):
            if not path.is_symlink():
                os.chown(path, identity.pw_uid, identity.pw_gid)
                if path.is_file(): path.chmod(0o600)
        paths = ','.join(map(str, (hr_overlay, overlay, args.runtime / 'addons')))
        base = ['sudo', '-u', 'odoo', '/usr/bin/python3.10', str(args.runtime / 'odoo-bin')]
        opts = ['-c', '/etc/dev_odoo18.conf', '-d', args.database, '--db-filter=^' + args.database + '$',
            '--db_host=/var/run/postgresql', '--addons-path=' + paths, '--data-dir=' + str(data),
            '--load=base,web', '--workers=0', '--max-cron-threads=0', '--no-http', '--without-demo=all']

        def execute(label, flags=(), expression=None):
            command = base + (['shell'] if expression is not None else []) + opts + list(flags) + ['--logfile=' + str(stage / (label + '.log'))]
            with (stage / (label + '-bootstrap.log')).open('x') as stream:
                status = subprocess.run(offline_odoo(command), input=expression, text=True, stdout=stream, stderr=subprocess.STDOUT)
            text = (stage / (label + '.log')).read_text(errors='replace')
            assert status.returncode == 0 and not re.search(r' (ERROR|CRITICAL) ', text), 'Inspect private ' + label + ' log'
            return text

        install = ('step_simpledigital_oca_security',) + HR_MODULES + FINANCE[:3] + (
            'step_l10n_cl_edi_core', 'step_batch_payment_grouping', 'step_batch_payment_core', 'step_l10n_cl_caf_storage')
        execute('install', ('-i', ','.join(install), '--stop-after-init'))
        probe = source / 'tools/community/probe_original_bootstrap.py'
        def inspect(label):
            expression = 'import runpy; runpy.run_path(' + repr(str(probe)) + ")[\"exercise\"](env," + repr(str(stage / (label + '.json'))) + ')'
            execute(label, expression=expression)
            return json.loads((stage / (label + '.json')).read_text())
        before = inspect('registry-before')
        text = execute('tests', ('-u', ','.join(install), '--test-enable', '--test-tags=' + TAGS, '--stop-after-init'))
        assert re.search(r'0 failed, 0 error\(s\) of 12 tests', text), 'All twelve real saved-input/batch cases must execute'
        after = inspect('registry-after')
        assert before == after, 'Cold registry/form/default/ACL contract changed after tests'
        assert packet(source) == frozen, 'Frozen source packet changed'
        counts = json.loads(sql(args.database, "SELECT json_build_object('installed',count(*),'enterprise',count(*) FILTER (WHERE license='OEEL-1')) FROM ir_module_module WHERE state='installed'"))
        assert counts == {'installed': 94, 'enterprise': 0}, 'Unexpected cold module graph'
        assert sql(args.database, "SELECT count(*) FROM ir_module_module WHERE name IN ('l10n_us','l10n_us_account') AND state='installed'") == '0', 'Demo-only US localizations unexpectedly installed'
        assert sql(args.database, "SELECT count(*) FROM ir_module_module WHERE state='installed' AND demo") == '0', 'Demo data was enabled'
        write(stage / 'passed.json', {'mode': 'community', 'profile': PROFILE, 'database': args.database,
            'counts': counts, 'package_files': len(frozen), 'source_files_sha256': hashlib.sha256((stage / 'source-files.json').read_bytes()).hexdigest(),
            'expected_test_count': 12, 'test_results': [line for line in text.splitlines() if 'tests.result' in line],
            'official_community_revision': OFFICIAL_PIN, 'oca_revision': PIN,
            'operational_package': False, 'historical_conversion': False, 'original_masters_imported': False,
            'simpledigital_certified': False, 'financial_certified': False, 'writes_to_source': False,
            'external_network_disabled': True, 'postgres_unix_socket': True, 'without_demo': 'all', 'demo_installed_modules': 0,
            'registry_forms_defaults_acl_verified': True, 'fixtures_rolled_back': True,
            'deferred_unpaid_membership_adopted': False, 'runner_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'probe_sha256': hashlib.sha256(probe.read_bytes()).hexdigest(),
            'bootstrap_derivation_sha256': hashlib.sha256((root / 'original-bootstrap-derivation.json').read_bytes()).hexdigest()})
        print('ORIGINAL_BOOTSTRAP_COMMUNITY_PASSED', flush=True)


if __name__ == '__main__':
    main()
