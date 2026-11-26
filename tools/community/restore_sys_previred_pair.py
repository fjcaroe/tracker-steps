"""Restore two private SyS SQL copies and prove preservation before starting Odoo."""

import argparse
import fcntl
import hashlib
import json
import os
import re
import shutil
import subprocess
from contextlib import closing
from pathlib import Path

from capture_sys_previred_stage import record_stage
from preflight_original_history_storage import capture, require


SOCKET = '/var/run/postgresql'
LOCK = '/run/lock/steps-environments.lock'
SOURCE = 'SyS'
GIB = 1024 ** 3


def pg(command, *args, readonly=False, **kwargs):
    env = {key: value for key, value in os.environ.items() if not key.startswith('PG')}
    if readonly:
        env['PGOPTIONS'] = '-c default_transaction_read_only=on'
    return subprocess.run(
        [command, '--host=' + SOCKET, '--username=postgres', '--no-password', *args],
        env=env, check=True, **kwargs,
    )


def query(database, sql):
    return pg('psql', '-XqAt', '-v', 'ON_ERROR_STOP=1', '--dbname=' + database,
              readonly=True, input=sql, text=True, stdout=subprocess.PIPE).stdout.strip()


def save(folder, filename, value):
    with (folder / filename).open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write('\n')


def restore_pair(folder, suffix):
    import psycopg2

    reference = 'MANAGEMENT_QA_SYS_PREVIRED_' + suffix
    candidate = 'COMMUNITY_SYS_PREVIRED_' + suffix
    require(re.fullmatch(r'[A-Z0-9_]{1,32}', suffix), 'sys-rehearsal-unsafe-suffix')
    with open(LOCK, 'rb') as lease:
        print('WAITING_FOR_STEPS_ENVIRONMENTS_LOCK', flush=True)
        fcntl.flock(lease, fcntl.LOCK_EX)
        folder.mkdir(mode=0o700, parents=False, exist_ok=False)
        with (folder / 'restore.log').open('xb') as log:
            restore_locked(folder, log, psycopg2, reference, candidate)


def restore_locked(folder, log, psycopg2, reference, candidate):
    require(query('postgres', "SELECT count(*) FROM pg_database "
                  f"WHERE datname IN ('{reference}', '{candidate}')") == '0',
            'sys-rehearsal-database-already-exists')
    data = Path(query('postgres', 'SHOW data_directory'))
    source_size = int(query('postgres', "SELECT pg_database_size('SyS')"))
    require(source_size > 0, 'sys-rehearsal-source-required')
    shared_volume = folder.stat().st_dev == data.stat().st_dev
    require(shutil.disk_usage(folder).free >= 2 * GIB + source_size,
            'sys-rehearsal-artifact-reserve')
    require(shutil.disk_usage(data).free >= 5 * GIB + (3 if shared_volume else 2) * source_size,
            'sys-rehearsal-postgresql-reserve')
    owner, encoding, collate, ctype = json.loads(query('postgres',
        "SELECT json_build_array(pg_get_userbyid(datdba), pg_encoding_to_char(encoding), "
        "datcollate, datctype) FROM pg_database WHERE datname = 'SyS'"))
    require(owner and not owner.startswith('-'), 'sys-rehearsal-source-owner-required')

    dump = folder / 'sys.dump'
    with dump.open('xb') as stream:
        pg('pg_dump', '-Fc', '--dbname=' + SOURCE, readonly=True, stdout=stream, stderr=log)
    with dump.open('rb') as stream:
        digest = hashlib.sha256()
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
        backup_sha = digest.hexdigest()
    save(folder, 'backup.json', {'source': SOURCE, 'sha256': backup_sha, 'bytes': dump.stat().st_size})

    baseline = None
    for database, stage in ((reference, 'reference-restored'), (candidate, 'candidate-restored')):
        require(shutil.disk_usage(data).free >= 5 * GIB + source_size
                and shutil.disk_usage(folder).free >= 2 * GIB, 'sys-rehearsal-reserve-before-restore')
        pg('createdb', '--owner=' + owner, '--template=template0', '--encoding=' + encoding,
           '--lc-collate=' + collate, '--lc-ctype=' + ctype, database, stderr=log)
        pg('pg_restore', '--exit-on-error', '--no-tablespaces', '--dbname=' + database,
           str(dump), stderr=log)
        save(folder, stage + '-preflight.json', capture(query, database, 'sys-previred'))
        with closing(psycopg2.connect(dbname=database, host=SOCKET, user='postgres')) as connection:
            connection.set_session(isolation_level='REPEATABLE READ', readonly=True)
            with connection.cursor() as cursor:
                receipt = record_stage(cursor, database, stage, backup_sha, baseline)
            connection.rollback()
        save(folder, stage + '.json', receipt)
        require(receipt['preserved'], 'sys-rehearsal-preservation-differs')
        baseline = (folder / 'reference-restored.json').read_bytes()
        print(stage, len(receipt['snapshot']['projections']),
              len(receipt['snapshot']['foreign_keys']), len(receipt['snapshot']['counters']), flush=True)
    print('SYS_SQL_PAIR_PRESERVED', backup_sha, flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--parent', type=Path, required=True)
    parser.add_argument('--suffix', required=True)
    args = parser.parse_args()
    require(re.fullmatch(r'[A-Z0-9_]{1,32}', args.suffix), 'sys-rehearsal-unsafe-suffix')
    os.umask(0o077)
    restore_pair(args.parent / ('sys-previred-' + args.suffix), args.suffix)


if __name__ == '__main__':
    main()
