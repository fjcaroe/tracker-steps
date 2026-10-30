"""Run the original native menu witness privately, offline and entirely RO.

Run explicitly as root on odoo-new only when the coordinator opens the lease
window. This separate runner leaves the existing master observer unchanged.
It accepts no actor, group, permission, SQL or alternate-entry override.
"""
import argparse
import configparser
import hashlib
import json
import os
from pathlib import Path
import subprocess


PRIVATE_ROOT = Path('/opt/steps-validation')
SOURCE_VISIBILITY_SHA256 = '6577c8c2d004778ce825e6427e3f4081080ccf15db8391febb18538082b42773'
IDENTITY_SHA256 = 'a9221233814c7bbb0c961c677453d38578e4202f45b0f2d7b7ebd9e5501784c1'
CAPSULE_SHA256 = '14b18ced97032ec27c306ed4c71c46f0c3d56e324d0eace4f0c8f2c86544e140'
SOURCE_DATABASE = 'MANAGEMENT_QA_CERRO_PAYROLL_API_ORIGINAL_REFERENCE_20261030S7'
TOOL_HASHES = {
    'original_external_references_readonly_bootstrap.py': {
        '60a7863ad1313648a68ebb938cd524216af1eb9d8bf8698b9a4ead0e215b68b2',
        'bdd12d4005b129d3e6a96034e2099a15c8598aa9a55007bfdea831b944dd7681'},
    'probe_original_master_visibility.py': {
        'b48f3310adde9899020f6b77d3207a0be73f35cb36e0affb27c9bd6e2fa9f5e1',
        '97f70446aa35138a3e4742de64e0f1669fc5531890b409e18d2d34b4125b3889'},
    'original_handover_visibility_contract.py': {
        'f067ac478133ec86ac658e44324613f935b2eb8252b1e240c2608e2b439b1857',
        'a7633d8ddaf0b486ee31c5928a8f308a92fcee1b279688473b79f319753a2b06'},
    'offline_process.py': {
        'aa4364c285ee2cdd9eee21249a9d4607e9bbe62b655e40e196872bb1d22b95c2',
        'ab6d002b0ca93c9f1d9dc316d424ebf5162b4d3273952b00ed6e6b36dac08f4f'},
    'probe_original_menu_visibility.py': {
        'abb67fb2de79fd09d842c4759c7eea14d9c856b6d4298e93657169f6ba63daa5',
        '47a67a2136fca473a984993daf1604c60c80ffc3562e1c882d984f04541a492b'},
}


def need(value, code):
    if not value:
        raise ValueError('native-menu-runner-' + code)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def explicit_actor(source):
    """The sealed, actually observed Source is the only actor selector."""
    actor = source.get('actor', {})
    companies = actor.get('allowed_company_ids')
    need(source.get('profile') == 'source-native-original-master-id-visibility'
        and source.get('database') == SOURCE_DATABASE
        and source.get('capsule_sha256') == CAPSULE_SHA256
        and source.get('normal_actor_source_visibility_proven') is True
        and source.get('database_writes') is False
        and source.get('source_model_code_overridden') is False,
        'sealed-original-source-contract-required')
    need(type(actor.get('uid')) is int and actor['uid'] > 1
        and isinstance(companies, list) and companies
        and all(type(value) is int and value > 0 for value in companies)
        and companies == sorted(set(companies))
        and actor.get('active_company_id') in companies
        and actor.get('superuser') is False and actor.get('system_group_member') is False
        and actor.get('original_native_payroll_manager') is True
        and actor.get('users_created') is False and actor.get('permissions_granted') is False,
        'existing-normal-actor-without-grants-required')
    return actor


def private_write(path, raw, owner):
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'wb') as stream:
        stream.write(raw)
    os.chown(path, owner.pw_uid, owner.pw_gid)


def private_copy(source, destination, digest, owner):
    need(source.is_file() and not source.is_symlink(), 'regular-source-file-required')
    raw = source.read_bytes()
    need(sha(raw) == digest, 'input-sha256-differs')
    private_write(destination, raw, owner)
    return digest


def shell_expression(output, source_tools):
    """Literal arguments only; no Source formulas, action execution or grants."""
    arguments = dict(capsule_path=str(output / 'capsule.json'), capsule_sha256=CAPSULE_SHA256,
        identity_path=str(output / 'identity.json'), identity_sha256=IDENTITY_SHA256,
        source_visibility_path=str(output / 'source-visibility.json'),
        source_visibility_sha256=SOURCE_VISIBILITY_SHA256, output=str(output / 'menus.json'))
    return '\n'.join((
        'import sys,json,os',
        'sys.path.insert(0,' + repr(str(source_tools)) + ')',
        'from probe_original_menu_visibility import run',
        'result=run(env,**' + repr(arguments) + ')',
        'import odoo.sql_db as _sq',
        'import odoo.modules.registry as _rg',
        "_cursors=list(_sq._steps_readonly_cursor_proof)",
        "assert _cursors and all(row['transaction_read_only']=='on' and row['odoo_cursor_readonly'] is True for row in _cursors)",
        "_sequence=_rg._steps_readonly_sequence_reader_proof",
        "assert _sequence['calls'] and _sequence['cursor_readonly_unchanged'] is True and _sequence['nextval_unchanged'] is True",
        "_proof={'schema':1,'profile':'source-native-menu-readonly-kernel','database':env.cr.dbname,'cursors':_cursors,'signaling_select_only':_sequence,'startup_and_observation_readonly':True,'registry_entry':'/opt/odoo18/odoo-bin','source_model_method_overrides':False,'isolated_readonly_signaling_reader':True,'database_writes':False}",
        '_path=' + repr(str(output / 'readonly-kernel.json')),
        "with os.fdopen(os.open(_path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'w') as _stream: _stream.write(json.dumps(_proof,indent=2))",
        "print('NATIVE_MENU_VISIBILITY', {key:value['visible_debug_false'] for key,value in result['menus'].items()})",
        '',
    ))


def native_command(database, output, source_tools, addons_path):
    need(database == SOURCE_DATABASE and addons_path, 'exact-private-source-and-original-addonpaths-required')
    return ['sudo', '-u', 'cerro_odoo18', 'env', 'PYTHONDONTWRITEBYTECODE=1',
        '/usr/bin/python3.10', str(source_tools / 'original_external_references_readonly_bootstrap.py'),
        '/opt/odoo18', '/opt/odoo18/odoo-bin', database, 'shell', '-c', '/etc/dev_odoo18.conf',
        '-d', database, '--db-filter=^' + database + '$', '--db_host=/var/run/postgresql',
        '--addons-path=' + addons_path, '--data-dir=' + str(output / 'data'), '--load=base,web',
        '--workers=0', '--max-cron-threads=0', '--no-http', '--without-demo=all',
        '--stop-after-init', '--logfile=' + str(output / 'native.log')]


def validate_runtime_results(menus, kernel, actor):
    need(menus.get('profile') == 'source-native-original-menu-visibility'
        and menus.get('schema') == 1 and menus.get('database') == SOURCE_DATABASE
        and menus.get('actor') == actor and menus.get('source_visibility_sha256') == SOURCE_VISIBILITY_SHA256
        and menus.get('capsule_sha256') == CAPSULE_SHA256 and menus.get('identity_sha256') == IDENTITY_SHA256
        and menus.get('probe_sha256') in TOOL_HASHES['probe_original_menu_visibility.py']
        and menus.get('debug') is False, 'actual-observer-result-contract-differs')
    for key in ('database_writes', 'source_method_overridden', 'permissions_granted', 'actions_executed',
            'historical_payroll_read', 'salary_amounts_read', 'salary_rules_evaluated',
            'target_menu_equivalence_certified', 'identity_conversion', 'all_products_operational', 'deadline_resolved'):
        need(menus.get(key) is False, 'unsafe-or-unproven-observer-flag:' + key)
    need(set(menus.get('menus', {})) == {'structure', 'rule', 'category', 'input_type'}
        and all(type(row.get('visible_debug_false')) is bool for row in menus['menus'].values()),
        'four-actual-menu-observations-required')
    need(kernel.get('profile') == 'source-native-menu-readonly-kernel'
        and kernel.get('schema') == 1 and kernel.get('database') == SOURCE_DATABASE
        and kernel.get('registry_entry') == '/opt/odoo18/odoo-bin'
        and kernel.get('source_model_method_overrides') is False
        and kernel.get('isolated_readonly_signaling_reader') is True
        and kernel.get('database_writes') is False and kernel.get('startup_and_observation_readonly') is True,
        'actual-readonly-kernel-result-required')
    cursors = kernel.get('cursors')
    need(isinstance(cursors, list) and cursors and all(row.get('database') in (SOURCE_DATABASE, 'postgres')
        and row.get('transaction_read_only') == 'on' and row.get('odoo_cursor_readonly') is True for row in cursors),
        'every-actual-startup-and-observer-cursor-must-be-readonly')
    sequence = kernel.get('signaling_select_only', {})
    need(sequence.get('original_get_sequences_sha256') == '6c41a6d4a995835a69a550420fbefb0987845008d8033035c96fea0670e5e000'
        and sequence.get('select_only_sql_sha256') == '641394a53615d5d518b5e6f7c8ba4f867036d3ba66b848be7ce5789c001dc52b'
        and sequence.get('calls') and all(row.get('database') == SOURCE_DATABASE
            and row.get('transaction_read_only') == 'on' and row.get('odoo_cursor_readonly') is True
            and row.get('pg_is_in_recovery') is False for row in sequence['calls'])
        and all(sequence.get(key) is True for key in ('cursor_readonly_unchanged', 'setup_signaling_unchanged',
            'signal_changes_unchanged', 'nextval_unchanged')) and sequence.get('installed_sources_modified') is False,
        'exact-audited-select-only-signaling-boundary-required')


def main():
    import fcntl
    import pwd
    import offline_process

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--tools', type=Path, required=True)
    parser.add_argument('--source-visibility', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    root, tools, output = args.root.resolve(), args.tools.resolve(), args.output.resolve()
    need(os.geteuid() == 0 and root.parent == PRIVATE_ROOT
        and root.name == 'community-original-handover-20261030S7'
        and tools.is_relative_to(PRIVATE_ROOT), 'root-and-explicit-private-source-required')
    need(output.parent == PRIVATE_ROOT and output.name.startswith('community-native-menu-visibility-')
        and not output.exists(), 'new-private-output-directory-required')
    stage = root / 'anchor'
    plan = json.loads((stage / 'handover-plan.json').read_bytes())
    need(plan['reference_database'] == SOURCE_DATABASE
        and plan['database'].replace('_HANDOVER_', '_REFERENCE_') == SOURCE_DATABASE,
        'original-source-plan-differs')
    proof_path = args.source_visibility.resolve()
    need(proof_path.is_relative_to(PRIVATE_ROOT) and proof_path.is_file() and not proof_path.is_symlink(),
        'private-source-visibility-file-required')
    raw_proof = proof_path.read_bytes()
    need(sha(raw_proof) == SOURCE_VISIBILITY_SHA256, 'actual-source6577-proof-required')
    actor = explicit_actor(json.loads(raw_proof))
    need(sha(Path(offline_process.__file__).read_bytes()) in TOOL_HASHES['offline_process.py'],
        'actually-imported-offline-wrapper-differs')
    # Validate every byte BEFORE making an output or starting an Odoo process.
    tool_bodies = {}
    for name, hashes in TOOL_HASHES.items():
        path = tools / name
        need(path.is_file() and not path.is_symlink(), 'regular-trusted-tool-required:' + name)
        raw = path.read_bytes()
        need(sha(raw) in hashes, 'trusted-tool-sha256-differs:' + name)
        tool_bodies[name] = raw
    for path, digest in ((stage / 'capsule.json', CAPSULE_SHA256), (stage / 'identity-before.json', IDENTITY_SHA256)):
        need(path.is_file() and not path.is_symlink() and sha(path.read_bytes()) == digest,
            'sealed-original-input-differs')
    source = configparser.ConfigParser(interpolation=None)
    need(source.read('/etc/odoo18-cerroelplomo.conf')
        and source['options']['db_name'] == 'CERRO_EL_PLOMO', 'original-addonpath-config-required')
    addons_path = source['options']['addons_path']
    owner = pwd.getpwnam('cerro_odoo18')
    output.mkdir(mode=0o750); os.chown(output, owner.pw_uid, owner.pw_gid)
    for directory in (output / 'data', output / 'tools'):
        directory.mkdir(mode=0o750); os.chown(directory, owner.pw_uid, owner.pw_gid)
    private_copy(stage / 'capsule.json', output / 'capsule.json', CAPSULE_SHA256, owner)
    private_copy(stage / 'identity-before.json', output / 'identity.json', IDENTITY_SHA256, owner)
    private_copy(proof_path, output / 'source-visibility.json', SOURCE_VISIBILITY_SHA256, owner)
    for name, raw in tool_bodies.items():
        private_write(output / 'tools' / name, raw, owner)
    private_write(output / 'native.log', b'', owner)
    os.umask(0o077)
    source_tools = output / 'tools'
    command = native_command(SOURCE_DATABASE, output, source_tools, addons_path)
    expression = shell_expression(output, source_tools)
    private_write(output / 'invocation.py', expression.encode(), owner)
    with open('/run/lock/steps-environments.lock', 'a') as lease:
        print('NATIVE_MENU_VISIBILITY_WAITING_FOR_LEASE', flush=True)
        fcntl.flock(lease, fcntl.LOCK_EX)
        with os.fdopen(os.open(output / 'bootstrap.log', os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w') as log:
            result = subprocess.run(offline_process.offline_odoo(command), input=expression, text=True,
                stdout=log, stderr=subprocess.STDOUT)
    receipt = {'schema': 1, 'profile': 'source-native-menu-runner', 'database': SOURCE_DATABASE,
        'runner_sha256': sha(Path(__file__).read_bytes()), 'returncode': result.returncode,
        'actor': actor, 'input_sha256': {'capsule.json': CAPSULE_SHA256, 'identity.json': IDENTITY_SHA256,
            'source-visibility.json': SOURCE_VISIBILITY_SHA256},
        'tools_sha256': {name: sha(raw) for name, raw in tool_bodies.items()},
        'invocation_sha256': sha(expression.encode()), 'source_inputs_copied': True,
        'copied_inputs_mode': '0600', 'copied_inputs_owner': 'cerro_odoo18',
        'shared_lease': '/run/lock/steps-environments.lock', 'external_network': False,
        'official_native_entry': '/opt/odoo18/odoo-bin', 'config': '/etc/dev_odoo18.conf',
        'actor_overrides_allowed': False, 'grants_allowed': False, 'source_model_method_overrides': False,
        'isolated_readonly_signaling_reader': True,
        'read_only_bootstrap_required': True, 'passed': False}
    for name in ('menus.json', 'readonly-kernel.json'):
        path = output / name
        if path.is_file():
            need(path.stat().st_uid == owner.pw_uid and path.stat().st_mode & 0o777 == 0o600,
                'runtime-output-custody-differs')
            receipt[name + '_sha256'] = sha(path.read_bytes())
    receipt['passed'] = result.returncode == 0 and all(name + '_sha256' in receipt
        for name in ('menus.json', 'readonly-kernel.json'))
    if receipt['passed']:
        try:
            validate_runtime_results(json.loads((output / 'menus.json').read_bytes()),
                json.loads((output / 'readonly-kernel.json').read_bytes()), actor)
        except ValueError as error:
            receipt['passed'] = False
            receipt['failure_code'] = str(error)
    private_write(output / 'runner-receipt.json', json.dumps(receipt, indent=2).encode(), owner)
    need(receipt['passed'], 'readonly-process-rejected-inspect-private-logs')
    print('NATIVE_MENU_VISIBILITY_COMPLETED', flush=True)


if __name__ == '__main__':
    main()
