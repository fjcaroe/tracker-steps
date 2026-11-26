"""Protect the original closed SyS payroll cohort during private ORM initialization."""
import argparse
from contextlib import closing
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re

import psycopg2

from admit_sys_payroll_storage import verify_bridge
from preflight_original_history_storage import require
from rehearse_sys_child_contracts import expect_rejection
from restore_sys_previred_pair import LOCK, SOCKET
from sys_previred_preservation import capture, identifier


PARENTS = {'hr_payslip': 'id', 'hr_payslip_line': 'slip_id',
           'hr_payslip_worked_days': 'payslip_id', 'hr_payslip_input': 'payslip_id'}
BASE = 'steps_sys_history_guard'


def guard_body(table, ids, columns):
    # Capture the original parents. State and foreign keys may themselves be
    # targeted by an initializer. Never derive protection from their new values.
    require(ids and all(type(i) is int and i > 0 for i in ids), 'sys-guard-invalid-cohort')
    parent = identifier(PARENTS[table])
    cohort = 'ARRAY[' + ','.join(map(str, ids)) + ']::integer[]'
    keys = ','.join("'" + identifier(k).strip('"') + "'" for k in sorted(columns))
    return f"""
DECLARE
    old_values jsonb;
    new_values jsonb;
BEGIN
    IF TG_OP = 'TRUNCATE' THEN
        RAISE EXCEPTION USING ERRCODE='23514', MESSAGE='SyS historical payroll: truncate forbidden';
    END IF;
    IF TG_OP != 'INSERT' AND OLD.{parent} = ANY({cohort}) THEN
        IF TG_OP = 'DELETE' THEN
            RAISE EXCEPTION USING ERRCODE='23514', MESSAGE='SyS historical payroll: delete forbidden';
        END IF;
        old_values := to_jsonb(OLD);
        new_values := to_jsonb(NEW);
        IF EXISTS (SELECT 1 FROM unnest(ARRAY[{keys}]) AS col(key)
                   WHERE old_values -> col.key IS DISTINCT FROM new_values -> col.key) THEN
            RAISE EXCEPTION USING ERRCODE='23514', MESSAGE='SyS historical payroll: original value changed';
        END IF;
        RETURN NEW;
    END IF;
    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    END IF;
    IF NEW.{parent} = ANY({cohort}) THEN
        RAISE EXCEPTION USING ERRCODE='23514', MESSAGE='SyS historical payroll: closed payslip';
    END IF;
    RETURN NEW;
END
"""


def install_or_verify(cr, snapshot, verify_only):
    cr.execute('LOCK TABLE ' + ','.join('public.' + identifier(t) for t in PARENTS)
               + ' IN SHARE ROW EXCLUSIVE MODE')
    cr.execute("SELECT id FROM public.hr_payslip WHERE state NOT IN ('draft','verify') OR paid ORDER BY id")
    cohort = [row[0] for row in cr.fetchall()]
    result = {}
    for table, parent in PARENTS.items():
        body = guard_body(table, cohort, snapshot['columns'][table])
        relation = 'public.' + identifier(table)
        function = 'public.' + identifier(BASE + '_' + table)
        if not verify_only:
            cr.execute(f'CREATE FUNCTION {function}() RETURNS trigger LANGUAGE plpgsql '
                       'SET search_path=pg_catalog AS %s', (body,))
            cr.execute(f'CREATE TRIGGER {BASE}_row BEFORE INSERT OR UPDATE OR DELETE ON {relation} '
                       f'FOR EACH ROW EXECUTE PROCEDURE {function}()')
            cr.execute(f'CREATE TRIGGER {BASE}_truncate BEFORE TRUNCATE ON {relation} '
                       f'FOR EACH STATEMENT EXECUTE PROCEDURE {function}()')
        cr.execute("""
            SELECT tgname, tgtype, tgenabled, prosrc, tgqual IS NULL AND tgnargs = 0
            FROM pg_catalog.pg_trigger t JOIN pg_catalog.pg_proc p ON p.oid=t.tgfoid
            WHERE tgrelid=%s::regclass AND tgfoid=%s::regprocedure ORDER BY tgname
        """, (relation, function + '()'))
        require(cr.fetchall() == [(BASE + '_row', 31, 'O', body, True),
                                  (BASE + '_truncate', 34, 'O', body, True)],
                'sys-guard-trigger-definition-drift:' + table)
        cr.execute(f'SELECT min(id),count(*) FROM {relation} WHERE {identifier(parent)}=ANY(%s)', (cohort,))
        sample, count = cr.fetchone()
        require(sample and count, 'sys-guard-historical-test-row-required:' + table)
        # Discard even the new MVCC tuple for the identical write.
        cr.execute('SAVEPOINT guard_probes')
        cr.execute(f'UPDATE {relation} SET name=name WHERE id=%s', (sample,))
        require(cr.rowcount == 1, 'sys-guard-identical-update-rejected')
        statements = (f"UPDATE {relation} SET name=coalesce(name,'') || 'x' WHERE id={sample}",
                      f'DELETE FROM {relation} WHERE id={sample}',
                      f'INSERT INTO {relation} SELECT * FROM {relation} WHERE id={sample}')
        for statement in statements:
            expect_rejection(cr, statement, '23514')
        cr.execute('ROLLBACK TO SAVEPOINT guard_probes')
        cr.execute('RELEASE SAVEPOINT guard_probes')
        result[table] = dict(rows=count, columns=len(snapshot['columns'][table]),
                             change_rejected=True, delete_rejected=True, insert_rejected=True)
    cr.execute('SAVEPOINT draft_probe')
    cr.execute("UPDATE public.hr_payslip SET name=coalesce(name,'') || 'x' WHERE id=(SELECT min(id) "
               "FROM public.hr_payslip WHERE state IN ('draft','verify') AND paid IS NOT TRUE)")
    require(cr.rowcount == 1, 'sys-guard-draft-mutation-rejected')
    cr.execute('ROLLBACK TO SAVEPOINT draft_probe')
    cr.execute('RELEASE SAVEPOINT draft_probe')
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--database', required=True)
    p.add_argument('--baseline', type=Path, required=True)
    p.add_argument('--admission', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--verify-only', action='store_true')
    args = p.parse_args()
    require(re.fullmatch(r'COMMUNITY_SYS_PREVIRED_(?:ADMISSION|COHORT)_[A-Z0-9_]{1,30}', args.database),
            'sys-guard-private-derivative-required')
    baseline = json.loads(args.baseline.read_bytes())
    admission_raw = args.admission.read_bytes()
    admission = json.loads(admission_raw)
    require(admission['database'] == args.database and admission['mode'] == 'restore-and-admit'
            and admission['backup_sha256'] == baseline['backup_sha256'] and baseline['preserved'] is True
            and baseline['stage'] == 'reference-restored' and baseline['snapshot']['database'] == admission['source'],
            'sys-guard-admitted-derivative-required')
    os.umask(0o077)
    with open(LOCK, 'rb') as lease:
        fcntl.flock(lease, fcntl.LOCK_EX)
        require(not args.output.exists(), 'sys-guard-receipt-exists')
        with closing(psycopg2.connect(dbname=args.database, host=SOCKET, user='postgres')) as db:
            original = baseline['snapshot']
            db.set_session(readonly=True, isolation_level='REPEATABLE READ')
            with db.cursor() as cr:
                before = capture(cr, args.database, original)
                verify_bridge(cr, original, before)
            db.rollback()
            db.set_session(readonly=False)
            with db:
                with db.cursor() as cr:
                    cr.execute("SET LOCAL lock_timeout='5s'")
                    result = install_or_verify(cr, before, args.verify_only)
            db.set_session(readonly=True)
            with db.cursor() as cr:
                after = capture(cr, args.database, original)
                require(before == after, 'sys-guard-originals-changed-during-probe')
        with args.output.open('x') as stream:
            json.dump(dict(database=args.database, tables=result, mode='verify' if args.verify_only else 'install',
                           admission_sha256=hashlib.sha256(admission_raw).hexdigest(), draft_edit_exercised=True,
                           backup_sha256=admission['backup_sha256'], source_projections_unchanged=True),
                      stream, sort_keys=True, indent=2)
            stream.write('\n')


if __name__ == '__main__':
    main()
