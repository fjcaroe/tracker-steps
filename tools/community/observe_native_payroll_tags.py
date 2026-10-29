"""Observe real native tags on a NEW clone of accepted private reference F.

This is a behavioral observation, not fresh-production acceptance or conversion.
Never upgrade modules, write to F, expose credentials or transmit bank/SII data.
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
import shutil
import subprocess

from validate_payroll_relation_storage import connect, snapshot

SOURCE_ROOT = Path('/opt/steps-validation/community-payroll-properties-20261029F')
SOURCE_DB = 'MANAGEMENT_QA_CERRO_PAYROLL_API_PROPERTIES_20261029F'


def run(*args, **kwargs):
    return subprocess.run(args, check=True, **kwargs)


def dump(path, data):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as stream:
        json.dump(data, stream, indent=2)


def baseline(database):
    with connect(database) as conn:
        with conn.cursor() as cursor:
            cursor.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
            values = snapshot(cursor)
    return {name: value for name, value in values.items()
            if 'sequence' not in value or re.fullmatch(r'ir_sequence_\d+(?:_\d+)?', name)}


def files(path):
    return {str(p.relative_to(path)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(path.rglob('*')) if p.is_file() and '__pycache__' not in p.parts}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--database', required=True)
    args = parser.parse_args()
    assert os.geteuid() == 0
    os.umask(0o077)
    root = args.root.resolve()
    assert Path('/opt/steps-validation') in root.parents and not root.exists()
    assert re.fullmatch(r'MANAGEMENT_QA_CERRO_TAG_OBSERVATION_[A-Za-z0-9_]+', args.database)
    stage = SOURCE_ROOT / 'cerro-reference'
    accepted = json.loads((stage / 'passed.json').read_text())
    assert accepted['database'] == SOURCE_DB and accepted['counts']['enterprise'] == 140
    packet = json.loads((stage / 'source-files.json').read_text())
    assert hashlib.sha256((stage / 'source-files.json').read_bytes()).hexdigest() == accepted['source_files_sha256']
    assert all(hashlib.sha256((SOURCE_ROOT / 'addons' / name).read_bytes()).hexdigest() == digest
               for name, digest in packet.items())
    config = configparser.ConfigParser(interpolation=None)
    assert config.read('/etc/odoo18-cerroelplomo.conf')
    identity = pwd.getpwnam('cerro_odoo18')
    root.mkdir(mode=0o700)
    payload_source = Path(__file__).with_name('probe_native_payroll_tags.py')
    payload = root / 'probe.py'
    payload.write_bytes(payload_source.read_bytes())
    store = stage / 'data/filestore' / SOURCE_DB
    assert store.is_dir() and not any(p.is_symlink() for p in store.rglob('*'))
    with open('/run/lock/steps-environments.lock', 'a') as lease:
        print('NATIVE_TAG_OBSERVATION_WAITING_FOR_SHARED_LEASE', flush=True)
        fcntl.flock(lease, fcntl.LOCK_EX)
        with connect('postgres') as conn:
            with conn.cursor() as cursor:
                cursor.execute('SELECT 1 FROM pg_database WHERE datname=%s', (args.database,))
                assert not cursor.fetchone()
                cursor.execute('SHOW data_directory')
                pgdir = Path(cursor.fetchone()[0])
        pg, disk = os.statvfs(pgdir), os.statvfs(root)
        assert pg.f_bavail * pg.f_frsize >= 5 * 1024**3
        assert disk.f_bavail * disk.f_frsize >= 2 * 1024**3
        source_before, source_files = baseline(SOURCE_DB), files(store)
        dump(root / 'source-before.json', source_before)
        dump(root / 'source-filestore.json', source_files)
        backup = root / 'source.dump'
        with backup.open('xb') as stream:
            run('sudo', '-u', 'postgres', 'pg_dump', '-Fc', SOURCE_DB, stdout=stream)
        with backup.open('rb') as stream, (root / 'decode.log').open('x') as log:
            run('sudo', '-u', 'postgres', 'pg_restore', '--file=/dev/null', stdin=stream,
                stdout=log, stderr=subprocess.STDOUT)
        run('sudo', '-u', 'postgres', 'createdb', '--owner=' + config['options']['db_user'], args.database)
        with backup.open('rb') as stream, (root / 'restore.log').open('x') as log:
            run('sudo', '-u', 'postgres', 'pg_restore', '--exit-on-error', '--no-owner', '--no-acl',
                '--no-comments', '--no-tablespaces', '--role=' + config['options']['db_user'],
                '-d', args.database, stdin=stream, stdout=log, stderr=subprocess.STDOUT)
        target_store = root / 'data/filestore' / args.database
        shutil.copytree(store, target_store)
        assert files(target_store) == source_files
        restored = baseline(args.database)
        assert restored == source_before, 'Fresh private clone differs from the accepted reference'
        dump(root / 'restored-before-neutralization.json', restored)
        neutralized = {}
        with connect(args.database) as conn:
            with conn.cursor() as cursor:
                for table in ('ir_cron', 'ir_mail_server'):
                    # F never ran cron workers. Addon installation can add new
                    # active cron definitions; neutralize this NEW clone only.
                    cursor.execute('UPDATE ' + table + ' SET active=false WHERE active RETURNING id')
                    neutralized[table] = sorted(row[0] for row in cursor.fetchall())
                    cursor.execute('SELECT count(*) FROM ' + table + ' WHERE active')
                    assert not cursor.fetchone()[0], 'Private reference is not neutralized'
                cursor.execute("SELECT count(*) FROM ir_module_module WHERE state IN ('to install','to upgrade','to remove')")
                assert not cursor.fetchone()[0]
        dump(root / 'neutralized-activation-ids.json', neutralized)
        before = baseline(args.database)
        assert set(before) == set(restored)
        assert all(before[name] == value for name, value in restored.items()
                   if name not in ('ir_cron', 'ir_mail_server')), 'Neutralization changed unrelated values'
        dump(root / 'before.json', before)
        for path in (root, *root.rglob('*')):
            os.chown(path, identity.pw_uid, identity.pw_gid)
        expression = ('import runpy,threading; threading.current_thread().testing=True; runpy.run_path(' + repr(str(payload)) + ')["observe"](env,'
                      + repr(str(root / 'observations.json')) + '); env.cr.rollback()')
        # The standard Odoo test marker suppresses automatic IAP enrichment.
        # A network namespace also makes accidental external I/O impossible;
        # PostgreSQL remains available only through its existing Unix socket.
        command = ['unshare', '--net', '--', 'sudo', '-u', 'cerro_odoo18', '/usr/bin/python3.10',
            str(SOURCE_ROOT / 'addons/tools/ops/run_agriculture_upgrade.py'), 'shell',
            '-c', '/etc/odoo18-cerroelplomo.conf', '-d', args.database,
            '--db_host=/var/run/postgresql',
            '--db-filter=^' + args.database + '$', '--addons-path=' + str(stage / 'addons') + ',' + config['options']['addons_path'],
            '--data-dir=' + str(root / 'data'), '--load=base,web', '--no-http', '--workers=0',
            '--max-cron-threads=0', '--logfile=' + str(root / 'probe.log')]
        with (root / 'bootstrap.log').open('x') as stream:
            status = subprocess.run(command, input=expression, text=True, stdout=stream, stderr=subprocess.STDOUT)
        after = baseline(args.database)
        dump(root / 'after.json', after)
        assert before == after, 'Observation changed business rows or counters'
        assert baseline(SOURCE_DB) == source_before and files(store) == source_files
        log = (root / 'probe.log').read_text(errors='replace')
        assert status.returncode == 0 and not re.search(r' (ERROR|CRITICAL) ', log)
        result = json.loads((root / 'observations.json').read_text())
        assert result['business_fixture_rolled_back'] and len(result['observations']) == 4
        dump(root / 'passed.json', dict(database=args.database, source_database=SOURCE_DB,
            backup_decoded=True, backup_sha256=hashlib.sha256(backup.read_bytes()).hexdigest(),
            original_contracts_preserved=len(before), source_unchanged=True, source_filestore_unchanged=True,
            payload_sha256=hashlib.sha256(payload.read_bytes()).hexdigest(),
            runner_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            observations_sha256=hashlib.sha256((root / 'observations.json').read_bytes()).hexdigest(),
            observation_only=True, isolated_network_namespace=True, postgres_unix_socket=True,
            official_test_thread_marker=True, fresh_production_acceptance=False, engine_converted=False, writes_to_source=False))
        print('NATIVE_PAYROLL_TAGS_OBSERVED 4 actual-engine cases; fixture rolled back', flush=True)


if __name__ == '__main__':
    main()
