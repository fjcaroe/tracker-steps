"""Inspect SyS historical admission on restored SQL and a private Community witness.

Run with the shared environment lock held. Report only counts, schema and
hashes. The Community witness describes the tested Cerro profile, not a
mapping of its masters or an authorization to initialize SyS.
"""

import argparse
from contextlib import closing
import json
import os
import re
from pathlib import Path

from capture_sys_previred_stage import record_stage
from preflight_original_history_storage import require, sha
from sys_previred_preservation import identifier, metadata_query


HISTORY = {
    'hr_payslip': ('basic_wage', 'gross_wage', 'net_wage'),
    'hr_payslip_line': ('amount', 'quantity', 'rate', 'total'),
    'hr_payslip_worked_days': ('amount', 'is_paid'),
    'hr_payslip_input': (),
}
CHILD_PARENT = {
    'hr_payslip_line': 'slip_id',
    'hr_payslip_worked_days': 'payslip_id',
    'hr_payslip_input': 'payslip_id',
}


def inspect_batch_journals(cursor):
    """Distinguish stored accounting evidence from current configuration."""
    cursor.execute("""
        WITH links AS (
            SELECT b.id AS batch_id, b.company_id AS expected_company,
                   b.move_id, true AS direct, false AS slip_company_conflict
            FROM public.hr_payslip_run b WHERE b.move_id IS NOT NULL
            UNION ALL
            SELECT b.id, b.company_id, p.move_id, false,
                   p.company_id IS DISTINCT FROM b.company_id
            FROM public.hr_payslip_run b
            JOIN public.hr_payslip p ON p.payslip_run_id = b.id
            WHERE p.move_id IS NOT NULL
        ), ledger AS (
            SELECT l.batch_id, bool_or(l.direct) AS has_direct_move,
                   bool_or(NOT l.direct) AS has_slip_move,
                   count(DISTINCT m.journal_id) AS journal_count,
                   bool_or(m.state = 'posted') AS has_posted_move,
                   bool_or(m.id IS NULL OR j.id IS NULL OR l.slip_company_conflict
                           OR m.company_id IS DISTINCT FROM l.expected_company
                           OR j.company_id IS DISTINCT FROM l.expected_company) AS needs_company_review
            FROM links l
            LEFT JOIN public.account_move m ON m.id = l.move_id
            LEFT JOIN public.account_journal j ON j.id = m.journal_id
            GROUP BY l.batch_id
        ), configuration AS (
            SELECT p.payslip_run_id AS batch_id, count(DISTINCT j.id) AS journal_count,
                   bool_and((j.company_id = b.company_id
                             AND p.company_id = b.company_id) IS TRUE) AS complete
            FROM public.hr_payslip p
            JOIN public.hr_payslip_run b ON b.id = p.payslip_run_id
            LEFT JOIN public.hr_payroll_structure s ON s.id = p.struct_id
            -- Company-dependent Odoo fields store explicit values by company.
            -- Defaults are not evidence about the current structure itself.
            LEFT JOIN public.account_journal j ON to_jsonb(j.id) =
                CASE WHEN jsonb_typeof(to_jsonb(s.journal_id)) = 'object'
                     THEN to_jsonb(s.journal_id) -> b.company_id::text
                     ELSE to_jsonb(s.journal_id)
                END
            GROUP BY p.payslip_run_id
        ), classified AS (
            SELECT b.state, coalesce(l.has_direct_move, false) AS has_direct_move,
                   coalesce(l.has_slip_move, false) AS has_slip_move,
                   coalesce(c.complete AND c.journal_count = 1, false) AS uniform_current_configuration,
                   CASE WHEN l.batch_id IS NULL THEN 'no_linked_move'
                        WHEN l.needs_company_review THEN 'journal_or_company_review'
                        WHEN l.journal_count <> 1 THEN 'conflicting_move_journals'
                        WHEN l.has_posted_move IS NOT TRUE THEN 'only_unposted_moves'
                        ELSE 'one_posted_journal'
                   END AS accounting_evidence
            FROM public.hr_payslip_run b
            LEFT JOIN ledger l ON l.batch_id = b.id
            LEFT JOIN configuration c ON c.batch_id = b.id
        )
        SELECT state, accounting_evidence, has_direct_move, has_slip_move,
               uniform_current_configuration, count(*)
        FROM classified GROUP BY 1,2,3,4,5 ORDER BY 1,2,3,4,5
    """)
    keys = ('state', 'accounting_evidence', 'has_direct_move', 'has_slip_move',
            'uniform_current_configuration', 'batches')
    return [dict(zip(keys, row)) for row in cursor.fetchall()]


def inspect_history(cursor, columns):
    findings = {}
    for table, fields in HISTORY.items():
        current = columns[table]
        missing = sorted(set(fields) - current.keys())
        relation = 'public.' + identifier(table) + ' h'
        slip = 'h'
        if table in CHILD_PARENT:
            slip = 's'
            relation += ' JOIN public.hr_payslip s ON s.id = h.' + identifier(CHILD_PARENT[table])
        paid = f' OR {slip}.paid IS TRUE' if 'paid' in columns['hr_payslip'] else ''
        counts = ['count(*)'] + [
            'count(*) FILTER (WHERE h.' + identifier(field) + ' IS NULL)'
            for field in fields if field in current
        ]
        cursor.execute('SELECT ' + ', '.join(counts) + ' FROM ' + relation
                       + f" WHERE ({slip}.state NOT IN ('draft', 'verify'){paid})")
        rows, *nulls = cursor.fetchone()
        findings[table] = {
            'closed_rows': rows,
            'missing_snapshot_columns': missing,
            'closed_nulls': dict(zip((field for field in fields if field in current), nulls)),
        }

    paths = {}
    for table, master, link in (
        ('hr_payslip_worked_days', 'hr_work_entry_type', 'work_entry_type_id'),
        ('hr_payslip_input', 'hr_payslip_input_type', 'input_type_id'),
    ):
        # Count links to current codes separately. A current code does not
        # attest what that code was when a payroll was finalized.
        cursor.execute(f"""
            SELECT count(*), count(c.id), count(*) FILTER (WHERE nullif(btrim(m.code), '') IS NOT NULL)
            FROM public.{table} h
            LEFT JOIN public.hr_payslip p ON p.id = h.payslip_id
            LEFT JOIN public.hr_contract c ON c.id = p.contract_id
                AND c.company_id = p.company_id AND c.employee_id = p.employee_id
            LEFT JOIN public.{master} m ON m.id = h.{link}
        """)
        rows, contract_links, current_codes = cursor.fetchone()
        paths[table] = {'rows': rows, 'matching_parent_contract': contract_links,
                        'linked_current_master_code': current_codes}
    return findings, paths


def inspect(source, target, database, witness, backup_sha, baseline, restored):
    require(database.startswith('COMMUNITY_SYS_PREVIRED_'), 'sys-admission-candidate-required')
    require(re.fullmatch(r'MANAGEMENT_QA_CERRO_PAYROLL_API_ORIGINAL_HANDOVER_[A-Za-z0-9_]+', witness),
            'sys-admission-private-cerro-witness-required')
    current = record_stage(source, database, 'candidate-restored', backup_sha, baseline)
    require(current == json.loads(restored) and current['preserved'], 'sys-admission-restoration-drift')
    target.execute("SET LOCAL search_path = pg_catalog, public")
    target.execute(metadata_query())
    comparison = target.fetchone()[0]
    require(comparison['database'] == witness and comparison['readonly'] == 'on'
            and comparison['isolation'] == 'repeatable read', 'sys-admission-readonly-witness-required')
    for cursor in (source, target):
        cursor.execute("SELECT count(*) FROM public.ir_module_module WHERE state LIKE 'to %'")
        require(cursor.fetchone()[0] == 0, 'sys-admission-pending-module-operation')
    target.execute("SELECT count(*) FROM public.ir_module_module WHERE state = 'installed' "
                   "AND (license = 'OEEL-1' OR name = 'hr_payroll')")
    require(target.fetchone()[0] == 0, 'sys-admission-community-witness-required')
    target.execute("SELECT count(*) FROM public.ir_module_module WHERE state = 'installed' AND name = 'payroll'")
    require(target.fetchone()[0] == 1, 'sys-admission-oca-witness-required')

    original = current['snapshot']['columns']
    differences = {}
    for table, fields in original.items():
        other = comparison['columns'].get(table, {})
        common = fields.keys() & other.keys()
        delta = {
            'source_only': sorted(fields.keys() - other.keys()),
            'witness_required_additions': sorted(name for name in other.keys() - fields.keys()
                                                 if other[name][1]),
            'type_changes': sorted(name for name in common if fields[name][0] != other[name][0]),
            'required_changes': sorted(name for name in common if fields[name][1] != other[name][1]),
        }
        if any(delta.values()):
            differences[table] = delta

    history, paths = inspect_history(source, original)
    return {
        'schema': 2, 'database': database, 'witness': witness, 'backup_sha256': backup_sha,
        'restored_receipt_sha256': sha(restored), 'restoration_matched': True,
        'differences': differences, 'history': history, 'existing_link_coverage': paths,
        'batch_journal_evidence': inspect_batch_journals(source),
        'upgrade_authorized': False,
    }


def main():
    from restore_sys_previred_pair import save

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', required=True)
    parser.add_argument('--witness', required=True)
    parser.add_argument('--backup', type=Path, required=True)
    parser.add_argument('--baseline', type=Path, required=True)
    parser.add_argument('--restored', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()

    import psycopg2

    backup = json.loads(args.backup.read_bytes())
    require(backup['source'] == 'SyS' and re.fullmatch(r'[0-9a-f]{64}', backup['sha256']),
            'sys-admission-backup-receipt-required')
    require(re.fullmatch(r'COMMUNITY_SYS_PREVIRED_[A-Za-z0-9_]+', args.database)
            and re.fullmatch(r'MANAGEMENT_QA_CERRO_PAYROLL_API_ORIGINAL_HANDOVER_[A-Za-z0-9_]+', args.witness),
            'sys-admission-private-databases-required')
    config = dict(host='/var/run/postgresql', user='postgres')
    with closing(psycopg2.connect(dbname=args.database, **config)) as source, closing(
        psycopg2.connect(dbname=args.witness, **config)
    ) as target:
        for connection in (source, target):
            connection.set_session(isolation_level='REPEATABLE READ', readonly=True)
        with source.cursor() as original, target.cursor() as witness:
            result = inspect(original, witness, args.database, args.witness, backup['sha256'],
                             args.baseline.read_bytes(), args.restored.read_bytes())
        source.rollback()
        target.rollback()
    os.umask(0o077)
    save(args.output.parent, args.output.name, result)


if __name__ == '__main__':
    main()
