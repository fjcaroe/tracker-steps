"""Retire only this ticket's superseded private databases; keep all snapshots.

Dry-run by default. Original environments, source.dump, filestores, test logs,
QA certificates, releases and deployment backups are never removed.
"""
import argparse
import fcntl
import hashlib
import json
from pathlib import Path
import subprocess


ROOT = Path('/opt/steps-validation')
PAIRS = [('development', tag) for tag in (
    '85ece0e4', '33d85d9a', '871fa549', 'd82e372f', 'c6a2bbf4',
    'd43f63c4', '6971b3cc', 'd94b5042')]
PAIRS += [(environment, tag) for environment in ('cerro', 'qa-cerro')
          for tag in ('c6a2bbf4', '6971b3cc')]


def sql(statement):
    return subprocess.check_output(['sudo', '-u', 'postgres', 'psql', '-XqAt',
        '-d', 'postgres', '-v', 'ON_ERROR_STOP=1', '-c', statement], text=True).strip()


def cleanup(apply):
    plan = []
    for environment, tag in PAIRS:
        database = 'MANAGEMENT_QA_' + environment.upper() + '_t229_' + tag
        stage = ROOT / ('management_' + environment + '_t229_' + tag)
        assert stage.resolve() == stage and stage.parent == ROOT and not stage.is_symlink()
        if sql("SELECT count(*) FROM pg_database WHERE datname='%s'" % database) == '0':
            continue
        assert stage.is_dir() and json.loads((stage/'baseline.json').read_text())
        snapshot = stage/'source.dump'
        assert snapshot.resolve() == snapshot and not snapshot.is_symlink()
        with snapshot.open('rb') as stream:
            assert stream.read(5) == b'PGDMP', 'A recoverable source snapshot is required'
        assert sql("SELECT count(*) FROM pg_stat_activity WHERE datname='%s'" % database) == '0', database+' is in use'
        plan.append({'database': database, 'stage': str(stage),
            'database_bytes': int(sql("SELECT pg_database_size('%s')" % database)),
            'snapshot_sha256': hashlib.sha256(snapshot.read_bytes()).hexdigest()})
    if apply:
        for item in plan:
            subprocess.run(['sudo', '-u', 'postgres', 'dropdb', '--', item['database']], check=True)
            (Path(item['stage'])/'private_database_removed.json').write_text(json.dumps(item, indent=2))
    print('T229_PRIVATE_COPY_CLEANUP '+json.dumps({'applied': apply, 'databases': plan,
        'snapshots_filestores_evidence_and_backups': 'retained'}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    with open('/run/lock/steps-environments.lock', 'a') as lease:
        fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
        cleanup(args.apply)
