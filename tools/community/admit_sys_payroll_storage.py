"""Restore a new SyS SQL derivative and commit its additive payroll bridge.

The caller supplies the original dump and its native reference receipt. The
control pair remains untouched. Reusing the derivative only verifies the
committed state, it cannot repair drift or reapply a partial admission.
"""
import argparse
from contextlib import closing
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil

import psycopg2

from capture_sys_previred_stage import record_stage
from preflight_original_history_storage import require
from rehearse_sys_child_contracts import rehearse_unknown_fields
from restore_sys_previred_pair import GIB, LOCK, SOCKET, pg, query
from sys_previred_preservation import capture, differences, identifier


def file_digest(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


ABSENT_FIELDS = {'hr_payslip_line': {'condition_select': 'character varying', 'condition_python': 'text'},
                 'hr_payslip_run': {'journal_id': 'integer'}}
PRIVATE_TABLESPACE = 'steps_community_storage_20261028_community'
RELATED = {
    ('hr.payslip.input', 'code'): ('char', True, 'input_type_id.code'),
    ('hr.payslip.input', 'contract_id'): ('many2one', True, 'payslip_id.contract_id'),
    ('hr.payslip.worked_days', 'code'): ('char', False, 'work_entry_type_id.code'),
    ('hr.payslip.worked_days', 'contract_id'): ('many2one', False, 'payslip_id.contract_id'),
    ('hr.payslip.line', 'amount_select'): ('selection', False, 'salary_rule_id.amount_select'),
}


def related_identity(cursor):
    found = {}
    for (model, field), expected in RELATED.items():
        cursor.execute("SELECT id,ttype,required,related,store FROM public.ir_model_fields "
                       "WHERE model=%s AND name=%s", (model, field))
        rows = cursor.fetchall()
        require(len(rows) == 1 and rows[0][1:] == (*expected, False), 'sys-admission-native-related-drift')
        found[model + '.' + field] = rows[0][0]
    return found


def verify_bridge(cursor, original, current):
    require(not any(differences(original, current).values()), 'sys-admission-original-drift')
    expected = {t: {f: [typ, False] for f, typ in fields.items()}
                for t, fields in ABSENT_FIELDS.items()}
    for model, field in RELATED:
        require(field not in current['columns'][model.replace('.', '_')], 'sys-admission-related-materialized')
    for table, columns in current['columns'].items():
        extra = {name: columns[name] for name in columns.keys() - original['columns'][table].keys()}
        require(extra == expected.get(table, {}), 'sys-admission-new-columns:' + table)
    fks = {'hr_payslip_run.hr_payslip_run_journal_id_fkey': [
        'FOREIGN KEY (journal_id) REFERENCES account_journal(id) ON DELETE RESTRICT', True]}
    actual = {k: v for k, v in current['foreign_keys'].items() if k not in original['foreign_keys']}
    require(actual == fks and current['counters'] == original['counters'],
            'sys-admission-additional-fk-or-counter-drift')
    for table, fields in ABSENT_FIELDS.items():
        populated = ' OR '.join(identifier(field) + ' IS NOT NULL' for field in fields)
        cursor.execute(f'SELECT count(*) FROM public.{identifier(table)} WHERE {populated}')
        require(cursor.fetchone()[0] == 0, 'sys-admission-unknown-history-overwritten:' + table)
    cursor.execute("SELECT count(*) FROM public.ir_module_module WHERE state LIKE 'to %%'")
    require(cursor.fetchone()[0] == 0, 'sys-admission-pending-module-changes')
    cursor.execute("SELECT name FROM public.ir_module_module WHERE state='installed' AND name IN "
                   "('hr_payroll','hr_payroll_account','l10n_cl_simpledigital_payroll','payroll','payroll_account')")
    require({row[0] for row in cursor.fetchall()} ==
            {'hr_payroll', 'hr_payroll_account', 'l10n_cl_simpledigital_payroll'},
            'sys-admission-native-provider-state-changed')


def run(args):
    require(re.fullmatch(r'COMMUNITY_SYS_PREVIRED_(?:ADMISSION|COHORT)_[A-Z0-9_]{1,30}', args.database),
            'sys-admission-private-derivative-required')
    backup = json.loads((args.source / 'backup.json').read_bytes())
    dump = args.source / 'sys.dump'
    require(backup['source'] == 'SyS' and backup['bytes'] == dump.stat().st_size
            and file_digest(dump) == backup['sha256'], 'sys-admission-dump-mismatch')
    baseline = (args.source / 'reference-restored.json').read_bytes()
    reference = json.loads(baseline)
    require(reference['stage'] == 'reference-restored' and reference['preserved'] is True
            and reference['backup_sha256'] == backup['sha256'], 'sys-admission-reference-mismatch')
    native = reference['snapshot']['database']
    require(re.fullmatch(r'MANAGEMENT_QA_SYS_PREVIRED_[A-Z0-9_]+', native),
            'sys-admission-native-reference-required')
    original = reference['snapshot']
    tablespace = getattr(args, 'tablespace', None)
    require(tablespace in (None, PRIVATE_TABLESPACE), 'sys-admission-unreviewed-tablespace')
    if not args.verify_only:
        size, owner, encoding, collate, ctype = json.loads(query('postgres',
            "SELECT json_build_array(pg_database_size(oid),pg_get_userbyid(datdba),"
            "pg_encoding_to_char(encoding),datcollate,datctype) FROM pg_database "
            f"WHERE datname='{native}'"))
        data = Path(query('postgres', 'SHOW data_directory'))
        target = data
        options = []
        if tablespace:
            target = Path(query('postgres', f"SELECT pg_tablespace_location(oid) FROM pg_tablespace WHERE spcname='{tablespace}'"))
            require(target.resolve().is_relative_to(Path('/opt/steps-validation/community-payroll-storage-20261028')),
                    'sys-admission-private-tablespace-path')
            options = ['--tablespace=' + tablespace]
        require(shutil.disk_usage(data).free >= 5 * GIB and shutil.disk_usage(target).free >= 5 * GIB + size,
                'sys-admission-insufficient-restore-space')
        # createdb fails if the exact name already exists. Never restore over it.
        pg('createdb', *options, '--owner=' + owner, '--template=template0', '--encoding=' + encoding,
           '--lc-collate=' + collate, '--lc-ctype=' + ctype, args.database)
        pg('pg_restore', '--exit-on-error', '--no-tablespaces', '--dbname=' + args.database, str(dump))
    summary = {}
    if tablespace:
        require(query('postgres', "SELECT t.spcname FROM pg_database d JOIN pg_tablespace t ON d.dattablespace=t.oid "
                      f"WHERE d.datname='{args.database}'") == tablespace, 'sys-admission-restore-tablespace-drift')
        summary['tablespace'] = tablespace
    with closing(psycopg2.connect(dbname=args.database, host=SOCKET, user='postgres')) as db:
        if not args.verify_only:
            db.set_session(readonly=True, isolation_level='REPEATABLE READ')
            with db.cursor() as cr:
                before = record_stage(cr, args.database, 'candidate-restored', backup['sha256'], baseline)
                require(before['preserved'], 'sys-admission-derivative-differs-from-backup')
                related_ids = related_identity(cr)
            db.rollback()
            db.set_session(readonly=False, isolation_level='REPEATABLE READ')
            with db:
                with db.cursor() as cr:
                    cr.execute("SET LOCAL search_path = pg_catalog, public")
                    cr.execute("SET LOCAL lock_timeout='5s'")
                    summary['unknown_history'] = rehearse_unknown_fields(cr, before['snapshot'], ABSENT_FIELDS)
        db.set_session(readonly=True, isolation_level='REPEATABLE READ')
        with db.cursor() as cr:
            current = capture(cr, args.database, original)
            verify_bridge(cr, original, current)
            summary['original_related_ids'] = related_identity(cr)
            if not args.verify_only:
                require(summary['original_related_ids'] == related_ids, 'sys-admission-related-id-drift')
        db.rollback()
    return dict(schema=1, database=args.database, source=native, backup_sha256=backup['sha256'],
                projections=len(original['projections']), original_fks=len(original['foreign_keys']),
                original_counters=len(original['counters']), new_columns=3, new_fks=1,
                mode='verify' if args.verify_only else 'restore-and-admit', odoo_started=False,
                filestore_restored=False, **summary)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--database', required=True)
    parser.add_argument('--verify-only', action='store_true')
    parser.add_argument('--tablespace', choices=[PRIVATE_TABLESPACE])
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    os.umask(0o077)
    with open(LOCK, 'rb') as lease:
        fcntl.flock(lease, fcntl.LOCK_EX)
        require(not args.output.exists(), 'sys-admission-receipt-exists')
        result = run(args)
        with args.output.open('x') as stream:
            json.dump(result, stream, indent=2, sort_keys=True)
            stream.write('\n')


if __name__ == '__main__':
    main()
