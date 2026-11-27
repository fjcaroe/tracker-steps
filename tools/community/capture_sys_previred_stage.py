"""Record a SyS storage checkpoint inside the coordinator's shared lock."""

import argparse
import json
import os
from contextlib import closing
from pathlib import Path

from preflight_original_history_storage import authorize, require, sha
from sys_previred_preservation import capture, differences


STAGES = ('reference-restored', 'candidate-restored', 'candidate-upgraded', 'candidate-rolled-back')


def record_stage(cursor, database, stage, backup_sha, baseline=None, previous=None):
    authorize(database, 'sys-previred')
    require(stage in STAGES, 'sys-preservation-invalid-stage')
    from_reference = stage == STAGES[0]
    prefix = 'MANAGEMENT_QA_SYS_PREVIRED_' if from_reference else 'COMMUNITY_SYS_PREVIRED_'
    require(database.startswith(prefix), 'sys-preservation-stage-database-mismatch')
    baseline_sha = None
    previous_sha = None
    reference = None
    if not from_reference:
        require(baseline is not None, 'sys-preservation-reference-receipt-required')
        baseline_sha = sha(baseline)
        reference = json.loads(baseline)
        require(reference['schema'] == 1 and reference['stage'] == STAGES[0]
                and reference['backup_sha256'] == backup_sha and reference['preserved'] is True
                and reference['snapshot']['database'].startswith('MANAGEMENT_QA_SYS_PREVIRED_'),
                'sys-preservation-reference-receipt-mismatch')
    if stage in STAGES[2:]:
        require(previous is not None, 'sys-preservation-previous-receipt-required')
        previous_sha = sha(previous)
        prior = json.loads(previous)
        require(prior['schema'] == 1 and prior['stage'] == STAGES[STAGES.index(stage) - 1]
                and prior['backup_sha256'] == backup_sha and prior['baseline_sha256'] == baseline_sha
                and prior['snapshot']['database'] == database and prior['preserved'] is True,
                'sys-preservation-previous-stage-mismatch')
    else:
        require(previous is None, 'sys-preservation-unexpected-previous-receipt')
    require(not from_reference or baseline is None, 'sys-preservation-unexpected-reference-receipt')

    original = reference['snapshot'] if reference else None
    snapshot = capture(cursor, database, original)
    changed = differences(original, snapshot) if original else {}
    if stage == 'candidate-restored':
        changed['added_columns'] = sorted(
            f'{table}.{name}' for table, columns in snapshot['columns'].items()
            for name in columns.keys() - original['columns'][table].keys())
        for key in ('foreign_keys', 'counters'):
            changed[f'added_{key}'] = sorted(snapshot[key].keys() - original[key].keys())
    return {
        'schema': 1, 'stage': stage, 'backup_sha256': backup_sha,
        'baseline_sha256': baseline_sha, 'previous_sha256': previous_sha,
        'snapshot': snapshot, 'differences': changed, 'preserved': not any(changed.values()),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', required=True)
    parser.add_argument('--stage', choices=STAGES, required=True)
    parser.add_argument('--backup-sha256', required=True)
    parser.add_argument('--baseline', type=Path)
    parser.add_argument('--previous', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    authorize(args.database, 'sys-previred')
    if len(args.backup_sha256) != 64 or any(c not in '0123456789abcdef' for c in args.backup_sha256):
        parser.error('expected a lowercase SHA-256 from the coordinator for the exact dump')
    baseline = args.baseline.read_bytes() if args.baseline else None
    previous = args.previous.read_bytes() if args.previous else None

    import psycopg2

    with closing(psycopg2.connect(dbname=args.database, host='/var/run/postgresql', user='postgres')) as db:
        db.set_session(isolation_level='REPEATABLE READ', readonly=True)
        with db.cursor() as cursor:
            receipt = record_stage(cursor, args.database, args.stage, args.backup_sha256, baseline, previous)
        db.rollback()

    fd = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8') as stream:
        json.dump(receipt, stream, indent=2, sort_keys=True)
        stream.write('\n')
    return 0 if receipt['preserved'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
