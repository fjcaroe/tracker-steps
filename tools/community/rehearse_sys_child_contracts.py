"""Rehearse the SyS child contract bridge on an isolated restored candidate.

The rehearsal always rolls back. It uses the original payslip's contract,
without consulting current payroll masters or populating unknown history.
"""

import argparse
from contextlib import closing
import json
import os
from pathlib import Path
import re

from capture_sys_previred_stage import record_stage
from preflight_original_history_storage import authorize, require
from sys_previred_preservation import identifier, metadata_query, projection_query


CHILDREN = ('hr_payslip_worked_days', 'hr_payslip_input')
LOCK = '/run/lock/steps-environments.lock'
UNKNOWN_FIELDS = {
    'hr_payslip_worked_days': {'code': 'character varying'},
    'hr_payslip_input': {'code': 'character varying'},
    'hr_payslip_line': {
        'amount_select': 'character varying', 'condition_select': 'character varying',
        'condition_python': 'text',
    },
    'hr_payslip_run': {'journal_id': 'integer'},
}


def preserved(connection, database, backup_sha, baseline, restored):
    connection.set_session(isolation_level='REPEATABLE READ', readonly=True)
    with connection.cursor() as cursor:
        receipt = record_stage(cursor, database, 'candidate-restored', backup_sha, baseline)
    connection.rollback()
    require(receipt == restored and receipt['preserved'], 'sys-contract-restoration-drift')


def expect_rejection(cursor, statement, expected_state):
    from psycopg2 import IntegrityError

    cursor.execute("SAVEPOINT contract_constraint")
    try:
        cursor.execute(statement)
    except IntegrityError as error:
        if error.pgcode != expected_state:
            raise
    else:
        raise ValueError('SyS payroll constraint accepted an invalid value')
    finally:
        cursor.execute("ROLLBACK TO SAVEPOINT contract_constraint")
        cursor.execute("RELEASE SAVEPOINT contract_constraint")


def verify_unknown_field_witness(cursor, witness):
    cursor.execute("SET LOCAL search_path = pg_catalog, public")
    cursor.execute(metadata_query())
    catalog = cursor.fetchone()[0]
    require(catalog['database'] == witness and catalog['readonly'] == 'on',
            'sys-history-private-readonly-witness-required')
    cursor.execute("""
        SELECT count(*) FILTER (WHERE license = 'OEEL-1' OR name = 'hr_payroll'),
               count(*) FILTER (WHERE name = 'payroll')
        FROM public.ir_module_module WHERE state = 'installed'
    """)
    require(cursor.fetchone() == (0, 1), 'sys-history-oca-community-witness-required')
    for table, fields in UNKNOWN_FIELDS.items():
        for field, sql_type in fields.items():
            require(catalog['columns'][table].get(field) == [sql_type, True],
                    f'sys-history-witness-column-drift:{table}.{field}')
    require(catalog['foreign_keys'].get('hr_payslip_run.hr_payslip_run_journal_id_fkey')
            == ['FOREIGN KEY (journal_id) REFERENCES account_journal(id) ON DELETE RESTRICT', True],
            'sys-history-witness-journal-fk-drift')


def rehearse_unknown_fields(cursor, snapshot):
    # Add columns without defaults: the old rows provide no historical value.
    cursor.execute("""
        LOCK TABLE public.hr_payslip_run, public.hr_payslip_line, public.account_journal
        IN ACCESS EXCLUSIVE MODE
    """)
    cursor.execute("""
        SELECT count(*) FROM pg_trigger
        WHERE tgrelid = 'public.hr_payslip_run'::regclass
          AND NOT tgisinternal AND tgenabled <> 'D'
    """)
    require(cursor.fetchone()[0] == 0, 'sys-history-unreviewed-batch-triggers')
    summaries = {}
    for table, fields in UNKNOWN_FIELDS.items():
        relation = 'public.' + identifier(table)
        original = snapshot['columns'][table]
        require(not fields.keys() & original.keys(), 'sys-history-new-columns-required:' + table)
        expected = snapshot['projections'][table]
        require(expected['rows'] > 0, 'sys-history-original-rows-required:' + table)
        declarations = ', '.join(
            f'ADD COLUMN {identifier(field)} {sql_type}' for field, sql_type in fields.items()
        )
        cursor.execute(f'ALTER TABLE {relation} {declarations}')
        for field in fields:
            column = identifier(field)
            cursor.execute(f'SELECT count(*) FROM {relation} WHERE {column} IS NULL')
            require(cursor.fetchone()[0] == expected['rows'], f'sys-history-nonnull:{table}.{field}')
            expect_rejection(cursor, f'ALTER TABLE {relation} ALTER COLUMN {column} SET NOT NULL', '23502')
        cursor.execute(projection_query(table, original))
        require(cursor.fetchone()[0] == expected, 'sys-history-original-projection-drift:' + table)
        summaries[table] = {'unknown_rows': expected['rows'], 'rejects_not_null': sorted(fields)}

    cursor.execute("""
        ALTER TABLE public.hr_payslip_run ADD CONSTRAINT hr_payslip_run_journal_id_fkey
        FOREIGN KEY (journal_id) REFERENCES public.account_journal(id) ON DELETE RESTRICT
    """)
    cursor.execute('SELECT min(id)::bigint - 1 FROM public.account_journal')
    missing = cursor.fetchone()[0]
    require(missing is not None and missing >= -2147483648, 'sys-history-journal-id-probe-unavailable')
    expect_rejection(cursor, f"""
        UPDATE public.hr_payslip_run SET journal_id = {missing}
        WHERE id = (SELECT min(id) FROM public.hr_payslip_run)
    """, '23503')
    return {'tables': summaries, 'journal_fk_rejects_unknown_master': True}


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
        update = (f'UPDATE {relation} SET contract_id = {{}} '
                  f'WHERE id = (SELECT min(id) FROM {relation})')
        expect_rejection(cursor, update.format('NULL'), '23502')
        expect_rejection(cursor, update.format(missing), '23503')
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
    parser.add_argument('--unknown-history-witness', help='Private Cerro OCA catalog for the nullable storage trial')
    args = parser.parse_args()
    authorize(args.database, 'sys-previred')
    require(args.database.startswith('COMMUNITY_SYS_PREVIRED_'), 'sys-contract-private-candidate-required')
    backup = json.loads(args.backup.read_bytes())
    require(backup['source'] == 'SyS', 'sys-contract-sys-backup-required')
    baseline = args.baseline.read_bytes()
    restored = json.loads(args.restored.read_bytes())
    with open(LOCK, 'rb') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        connection = {'host': '/var/run/postgresql', 'user': 'postgres'}
        witness = args.unknown_history_witness
        if witness:
            require(re.fullmatch(r'MANAGEMENT_QA_CERRO_PAYROLL_API_ORIGINAL_HANDOVER_[A-Za-z0-9_]+', witness),
                    'sys-history-private-witness-required')
            with closing(psycopg2.connect(dbname=witness, **connection)) as catalog:
                catalog.set_session(isolation_level='REPEATABLE READ', readonly=True)
                with catalog.cursor() as cursor:
                    verify_unknown_field_witness(cursor, witness)
        result = {'schema': 1, 'database': args.database, 'backup_sha256': backup['sha256']}
        with closing(psycopg2.connect(dbname=args.database, **connection)) as db:
            preserved(db, args.database, backup['sha256'], baseline, restored)
            db.set_session(isolation_level='REPEATABLE READ', readonly=False)
            try:
                with db.cursor() as cursor:
                    links = rehearse(cursor, restored['snapshot'])
                    if witness:
                        result['unknown_history'] = rehearse_unknown_fields(cursor, restored['snapshot'])
                        result['witness'] = witness
            finally:
                db.rollback()
            preserved(db, args.database, backup['sha256'], baseline, restored)

        os.umask(0o077)
        save(args.output.parent, args.output.name, result | {
            'links': links, 'restored_receipt_matched_after_rollback': True,
            'upgrade_authorized': False,
        })


if __name__ == '__main__':
    main()
