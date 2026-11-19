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


def cleanup(apply, include_completed_final=False):
    pairs = list(PAIRS)
    if include_completed_final:
        # Final copies are retired only after all three publications have receipts.
        for environment in ('development', 'cerro', 'qa-cerro'):
            stage = ROOT / ('management_' + environment + '_t229_d94b5042_r1')
            proof = json.loads((stage/'qa_passed.json').read_text())
            assert proof['commit'] == 'd94b5042a3d9b1874827567f8e212a543e435744'
            assert proof['release_sha256'] == 'dacfaf3974fb99748b3e0232cd8de2cd175ded6e637f3f0ba2a653d8f20a9dcf'
            assert 'MANAGEMENT_REGISTRY_OK' in (stage/('verify-'+proof['database']+'.log')).read_text()
            receipts = [json.loads(path.read_text()) for path in
                Path('/opt/steps_backups').glob('management_'+environment+'_'+ '*'+'/deployment.json')]
            assert any(receipt.get('commit') == proof['commit'] and
                receipt.get('sha256') == proof['release_sha256'] for receipt in receipts)
            pairs.append((environment, 'd94b5042_r1'))
    plan = []
    for environment, tag in pairs:
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
    parser.add_argument('--include-completed-final', action='store_true',
        help='Also retire the final copies after all three exact publication receipts exist')
    args = parser.parse_args()
    with open('/run/lock/steps-environments.lock', 'a') as lease:
        fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
        cleanup(args.apply, args.include_completed_final)
