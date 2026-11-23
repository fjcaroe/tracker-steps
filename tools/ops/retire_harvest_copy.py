"""Retire completed harvest private databases, retaining dumps, filestores and proof.

Dry-run by default; original environments and unrelated tickets are never selected.
"""
import argparse
import fcntl
import hashlib
import json
from pathlib import Path
import re
import subprocess


def sql(statement):
    return subprocess.check_output(['sudo', '-u', 'postgres', 'psql', '-XqAt',
        '-d', 'postgres', '-v', 'ON_ERROR_STOP=1', '-c', statement], text=True).strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stages', nargs='+', type=Path)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--failed-unit', help='Exact inactive private QA unit, for a failed copy without a certificate')
    args = parser.parse_args()
    plan = []
    with open('/run/lock/steps-environments.lock', 'a') as lease:
        fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
        for stage in args.stages:
            assert stage.resolve() == stage and stage.parent == Path('/opt/steps-validation')
            match = re.fullmatch(r'management_(development|cerro|qa-cerro)_(t231|t232|t231232)_([0-9a-f]{8})', stage.name)
            assert match and not stage.is_symlink()
            environment, ticket, commit_prefix = match.groups()
            database = 'MANAGEMENT_QA_' + environment.upper() + '_' + ticket + '_' + commit_prefix
            if args.failed_unit:
                assert len(args.stages) == 1 and environment == 'development'
                assert args.failed_unit == 'steps-'+ticket+'-qa-dev-'+commit_prefix
                state = subprocess.check_output(['systemctl', 'show', '--value', '--property=ActiveState', args.failed_unit], text=True).strip()
                assert state in ('failed', 'inactive')
                assert not (stage/'qa_passed.json').exists()
                logs = list(stage.glob('qa-*.log'))
                assert len(logs) == 1 and re.search(r'\b[1-9][0-9]* error\(s\)', logs[0].read_text())
            else:
                proof = json.loads((stage/'qa_passed.json').read_text())
                assert proof['database'] == database and proof['commit'].startswith(commit_prefix)
                assert 'MANAGEMENT_REGISTRY_OK' in (stage/('verify-'+database+'.log')).read_text()
            snapshot = stage/'source.dump'
            assert snapshot.resolve() == snapshot and not snapshot.is_symlink()
            with snapshot.open('rb') as stream:
                assert stream.read(5) == b'PGDMP'
            if sql("SELECT count(*) FROM pg_database WHERE datname='%s'" % database) == '0':
                continue
            assert sql("SELECT count(*) FROM pg_stat_activity WHERE datname='%s'" % database) == '0'
            plan.append({'database': database, 'stage': str(stage),
                'snapshot_sha256': hashlib.sha256(snapshot.read_bytes()).hexdigest()})
        if args.apply:
            for item in plan:
                subprocess.run(['sudo', '-u', 'postgres', 'dropdb', '--', item['database']], check=True)
                (Path(item['stage'])/'private_database_removed.json').write_text(json.dumps(item, indent=2))
    print('HARVEST_PRIVATE_COPIES_RETIRED '+json.dumps({'applied': args.apply, 'databases': plan,
        'snapshots_filestores_and_proofs': 'retained'}))


if __name__ == '__main__':
    main()
