"""Capture physical field bindings in accepted private registries, read-only.

Default PostgreSQL read-only is enabled BEFORE registry startup. A startup
write fails; it is never retried in read-write mode. No upgrades, services,
business-record access, callable evaluation or source-body inspection.
"""
import argparse
import configparser
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess


PROFILES = {
    ('community-multifront-20261030H', 'community'): ('COMMUNITY_PAYROLL_API_MULTIFRONT_20261030H', 576),
    ('community-multifront-parallel-20261030D', 'community'): ('COMMUNITY_PAYROLL_API_PARALLEL_20261030D', 637),
    ('community-multifront-parallel-20261030D', 'cerro-reference'): ('MANAGEMENT_QA_CERRO_PAYROLL_API_PARALLEL_20261030D', 437),
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(value, message):
    if not value:
        raise ValueError(message)


def authorize(root, mode, accepted):
    profile = PROFILES.get((root.name, mode))
    require(profile is not None and (accepted.get('database'), accepted.get('expected_test_count')) == profile,
        'Only the explicitly accepted private H/D profiles are admitted')
    require(accepted.get('mode') == mode and accepted.get('writes_to_source') is False
        and re.fullmatch('[0-9a-f]{64}', accepted.get('source_files_sha256', '')),
        'The accepted source receipt is incomplete')
    return profile[0]


def readonly_command(command):
    """Apply the connection policy after sudo and before Python imports Odoo."""
    return command[:3] + ['env', 'PGOPTIONS=-c default_transaction_read_only=on',
        'PYTHONDONTWRITEBYTECODE=1'] + command[3:]


def main():
    import fcntl
    import pwd
    import psycopg2
    from offline_process import offline_odoo
    from validate_payroll_relation_storage import snapshot

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True, type=Path)
    parser.add_argument('--mode', choices=('community', 'cerro-reference'), required=True)
    parser.add_argument('--runtime', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    require(os.geteuid() == 0, 'Private root coordinator required')
    root, output, runtime = args.root.resolve(), args.output.resolve(), args.runtime.resolve()
    private = Path('/opt/steps-validation')
    require(root.parent == private and root.is_dir() and output.is_relative_to(private / 'community-original-closure-20261030')
        and not output.exists() and output.parent.is_dir(), 'New isolated private output required')
    stage, source = root / args.mode, root / 'addons'
    accepted_path, files_path = stage / 'passed.json', stage / 'source-files.json'
    accepted = json.loads(accepted_path.read_text())
    database = authorize(root, args.mode, accepted)
    fingerprints = json.loads(files_path.read_text())
    for name, digest in fingerprints.items():
        path = source / name
        require(path.resolve().is_relative_to(source.resolve()) and sha(path) == digest,
            'Accepted source byte differs: ' + name)
    pure = args.mode == 'community'
    config_path = '/etc/dev_odoo18.conf' if pure else '/etc/odoo18-cerroelplomo.conf'
    config = configparser.ConfigParser(interpolation=None)
    require(config.read(config_path), 'Existing runtime config required')
    user = 'odoo' if pure else 'cerro_odoo18'
    identity = pwd.getpwnam(user)
    helper = Path(__file__).with_name('original_external_references_registry.py')
    bootstrap = Path(__file__).with_name('original_external_references_readonly_bootstrap.py')
    require(helper.is_file() and bootstrap.is_file(), 'Versioned metadata payload and pool policy required')
    output.mkdir(mode=0o700)
    os.chown(output, identity.pw_uid, identity.pw_gid)
    previous_umask = os.umask(0o077)

    def dump(name, value):
        with os.fdopen(os.open(output / (name + '.json'), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w') as stream:
            json.dump(value, stream, indent=2, sort_keys=True)

    local_helper = output / helper.name
    with os.fdopen(os.open(local_helper, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'wb') as stream:
        stream.write(helper.read_bytes())
    os.chown(local_helper, identity.pw_uid, identity.pw_gid)
    local_bootstrap = output / bootstrap.name
    with os.fdopen(os.open(local_bootstrap, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'wb') as stream:
        stream.write(bootstrap.read_bytes())
    os.chown(local_bootstrap, identity.pw_uid, identity.pw_gid)

    def baseline():
        os.seteuid(pwd.getpwnam('postgres').pw_uid)
        try:
            connection = psycopg2.connect(dbname=database, user='postgres', host='/var/run/postgresql',
                options='-c default_transaction_read_only=on')
        finally:
            os.seteuid(0)
        with connection:
            with connection.cursor() as cursor:
                cursor.execute('SHOW transaction_read_only')
                require(cursor.fetchone() == ('on',), 'Snapshot connection must start read-only')
                cursor.execute("SELECT count(*) FROM ir_module_module WHERE state IN ('to install','to upgrade','to remove')")
                require(cursor.fetchone()[0] == 0, 'Pending module operation; never start this registry')
                values = snapshot(cursor)
        connection.close()
        return values

    def protected(values):
        # Every physical table and every original business numbering sequence.
        return {name: value for name, value in values.items() if 'sequence' not in value
            or re.fullmatch(r'ir_sequence_\d+(?:_\d+)?', name)}

    expression = ('import runpy,json,os; env.cr.rollback(); env.cr.execute("SHOW transaction_read_only"); '
        'assert env.cr.fetchone()==("on",), "Registry must start read-only"; '
        'assert env.cr.readonly is True, "Real Odoo cursor must be read-only"; '
        'report=runpy.run_path(' + repr(str(local_helper)) + ')["inspect_registry"](env, '
        'source_packet_sha256=' + repr(accepted['source_files_sha256']) + ', '
        'acceptance_sha256=' + repr(sha(accepted_path)) + '); '
        'fd=os.open(' + repr(str(output / 'registry.json')) + ',os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600); '
        'stream=os.fdopen(fd,"w"); json.dump(report,stream,indent=2,sort_keys=True); stream.close(); env.cr.rollback()')
    paths = str(stage / 'addons') + ',' + (str(runtime / 'addons') if pure else config['options']['addons_path'])
    if pure:
        paths = str(stage / 'consumer-addons') + ',' + paths
    entry = runtime / 'odoo-bin' if pure else source / 'tools/ops/run_agriculture_upgrade.py'
    odoo_runtime = runtime if pure else Path('/opt/odoo18')
    command = ['sudo', '-u', user, '/usr/bin/python3.10', str(local_bootstrap), str(odoo_runtime), str(entry), 'shell', '-c', config_path,
        '-d', database, '--db-filter=^' + database + '$', '--addons-path=' + paths,
        '--db_host=/var/run/postgresql', '--data-dir=' + str(stage / 'data'), '--load=base,web',
        '--workers=0', '--max-cron-threads=0', '--no-http', '--http-interface=127.0.0.1',
        '--http-port=0', '--gevent-port=0', '--logfile=' + str(output / 'registry.log')]
    try:
        with open('/run/lock/steps-environments.lock', 'a') as lease:
            fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
            before = baseline()
            dump('business-before', before)
            try:
                with (output / 'bootstrap.log').open('x') as stream:
                    status = subprocess.run(offline_odoo(readonly_command(command)), input=expression,
                        text=True, stdout=stream, stderr=subprocess.STDOUT)
            finally:
                after = baseline()
                dump('business-after', after)
                require(protected(before) == protected(after), 'Registry changed original table values or business counters')
            require(status.returncode == 0 and (output / 'registry.json').is_file(),
                'Read-only startup failed; inspect private logs, never retry in read-write')
            log = (output / 'registry.log').read_text(errors='replace')
            require(not re.search(r' (ERROR|CRITICAL) ', log), 'Registry logged a failure; never certify this probe')
            report = json.loads((output / 'registry.json').read_text())
            require(report['read_only'] is True and all(report[name] is False for name in
                ('orm_records_accessed', 'callables_executed', 'source_bodies_read', 'database_writes', 'adoption_authorized')),
                'Metadata payload scope differs')
            dump('passed', {'schema': 1, 'database': database, 'mode': args.mode,
                'exact_tables_and_business_counters_preserved': len(protected(before)),
                'all_infrastructure_sequences_also_exact': before == after,
                'read_only_before_registry_startup': True, 'upgraded': False,
                'external_network_disabled': True, 'postgres_unix_socket': True,
                'source_packet_sha256': accepted['source_files_sha256'],
                'acceptance_sha256': sha(accepted_path), 'source_files_json_sha256': sha(files_path),
                'runner_sha256': sha(__file__), 'payload_sha256': sha(helper),
                'readonly_bootstrap_sha256': sha(bootstrap), 'odoo_pool_readonly_before_connect': True,
                'registry_json_sha256': sha(output / 'registry.json'), 'adoption_authorized': False})
    except Exception as error:
        dump('failed', {'schema': 1, 'database': database, 'error': str(error), 'read_only_required_from_startup': True,
            'read_write_retry_authorized': False, 'adoption_authorized': False})
        raise
    finally:
        os.umask(previous_umask)
    print('ORIGINAL_EXTERNAL_REGISTRY_READONLY_OK ' + args.mode)


if __name__ == '__main__':
    main()
