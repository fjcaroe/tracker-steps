"""Rehearse the SyS child contract bridge on an isolated restored candidate.

The rehearsal always rolls back. It uses the original payslip's contract,
without consulting current payroll masters or populating unknown history.
"""

import argparse
from contextlib import closing
import json
import os
from pathlib import Path

from capture_sys_previred_stage import record_stage
from preflight_original_history_storage import authorize, require
from sys_previred_preservation import identifier, projection_query


CHILDREN = ('hr_payslip_worked_days', 'hr_payslip_input')
LOCK = '/run/lock/steps-environments.lock'


def preserved(connection, database, backup_sha, baseline, restored):
    connection.set_session(isolation_level='REPEATABLE READ', readonly=True)
    with connection.cursor() as cursor:
        receipt = record_stage(cursor, database, 'candidate-restored', backup_sha, baseline)
    connection.rollback()
    require(receipt == restored and receipt['preserved'], 'sys-contract-restoration-drift')


def probe_constraint(cursor, relation, invalid, expected_state):
    from psycopg2 import IntegrityError

    cursor.execute("SAVEPOINT contract_constraint")
    try:
        cursor.execute(f'UPDATE {relation} SET contract_id = {invalid} '
                       f'WHERE id = (SELECT min(id) FROM {relation})')
    except IntegrityError as error:
        if error.pgcode != expected_state:
            raise
    else:
        raise ValueError('SyS child contract constraint accepted an invalid value')
    finally:
        cursor.execute("ROLLBACK TO SAVEPOINT contract_constraint")
        cursor.execute("RELEASE SAVEPOINT contract_constraint")


def rehearse(cursor, snapshot):
    cursor.execute("SET LOCAL search_path = pg_catalog, public")
    cursor.execute("SET LOCAL lock_timeout = '5s'")
    cursor.execute("SELECT current_database(), NOT pg_is_in_recovery()")
    require(cursor.fetchone() == (snapshot['database'], True), 'sys-contract-candidate-identity')

    cursor.execute("""
        LOCK TABLE public.hr_payslip_worked_days, public.hr_payslip_input,
                   public.hr_payslip, public.hr_contract IN ACCESS EXCLUSIVE MODE
    """)
    cursor.execute("""
        SELECT count(*) FROM pg_trigger
        WHERE tgrelid IN ('public.hr_payslip_worked_days'::regclass,
                          'public.hr_payslip_input'::regclass)
              AND NOT tgisinternal AND tgenabled <> 'D'
    """)
    require(cursor.fetchone()[0] == 0, 'sys-contract-unreviewed-user-triggers')

    cursor.execute("SELECT min(id)::bigint - 1 FROM public.hr_contract")
    missing = cursor.fetchone()[0]
    require(missing is not None and missing >= -2147483648, 'sys-contract-missing-id-for-fk-probe')
    summary = {}
    for table in CHILDREN:
        original = snapshot['columns'][table]
        require('contract_id' not in original, 'sys-contract-new-column-required')
        expected = snapshot['projections'][table]
        require(expected['rows'] > 0, 'sys-contract-original-child-rows-required')
        relation = 'public.' + identifier(table)
        constraint = identifier(table + '_contract_id_fkey')
        cursor.execute(f'ALTER TABLE {relation} ADD COLUMN contract_id integer')
        cursor.execute(f"""
            UPDATE {relation} child
            SET contract_id = contract.id
            FROM public.hr_payslip slip
            JOIN public.hr_contract contract ON contract.id = slip.contract_id
                AND contract.employee_id = slip.employee_id
                AND contract.company_id = slip.company_id
            WHERE slip.id = child.payslip_id
        """)
        require(cursor.rowcount == expected['rows'], 'sys-contract-incomplete-parent-link:' + table)
        cursor.execute(f'ALTER TABLE {relation} ALTER COLUMN contract_id SET NOT NULL')
        cursor.execute(f'ALTER TABLE {relation} ADD CONSTRAINT {constraint} '
                       'FOREIGN KEY (contract_id) REFERENCES public.hr_contract(id) ON DELETE RESTRICT')
        probe_constraint(cursor, relation, 'NULL', '23502')
        probe_constraint(cursor, relation, str(missing), '23503')
        cursor.execute(f"""
            SELECT count(*) FROM {relation} child
            JOIN public.hr_payslip slip ON slip.id = child.payslip_id
            WHERE child.contract_id = slip.contract_id
        """)
        require(cursor.fetchone()[0] == expected['rows'], 'sys-contract-bridge-verification:' + table)
        cursor.execute(projection_query(table, original))
        require(cursor.fetchone()[0] == expected, 'sys-contract-original-projection-drift:' + table)
        summary[table] = {'verified_links': expected['rows'], 'rejects_null': True,
                          'rejects_unknown_contract': True, 'original_projection_preserved': True}
    return summary


def main():
    import fcntl
    import psycopg2

    from restore_sys_previred_pair import save

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', required=True)
    parser.add_argument('--backup', type=Path, required=True)
    parser.add_argument('--baseline', type=Path, required=True)
    parser.add_argument('--restored', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    authorize(args.database, 'sys-previred')
    require(args.database.startswith('COMMUNITY_SYS_PREVIRED_'), 'sys-contract-private-candidate-required')
    backup = json.loads(args.backup.read_bytes())
    require(backup['source'] == 'SyS', 'sys-contract-sys-backup-required')
    baseline = args.baseline.read_bytes()
    restored = json.loads(args.restored.read_bytes())
    with open(LOCK, 'rb') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with closing(psycopg2.connect(dbname=args.database, host='/var/run/postgresql', user='postgres')) as db:
            preserved(db, args.database, backup['sha256'], baseline, restored)
            db.set_session(isolation_level='REPEATABLE READ', readonly=False)
            try:
                with db.cursor() as cursor:
                    links = rehearse(cursor, restored['snapshot'])
            finally:
                db.rollback()
            preserved(db, args.database, backup['sha256'], baseline, restored)

        os.umask(0o077)
        save(args.output.parent, args.output.name, {
            'schema': 1, 'database': args.database, 'backup_sha256': backup['sha256'],
            'links': links, 'restored_receipt_matched_after_rollback': True,
            'upgrade_authorized': False,
        })


if __name__ == '__main__':
    main()
