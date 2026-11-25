"""Negative admission tests; no Odoo, SQL connection or business fixtures."""
from copy import deepcopy
import json
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

import probe_original_handover as probe


INSERT = '''INSERT INTO hr_structure_salary_rule_rel (struct_id,rule_id)
    SELECT * FROM unnest(%s::integer[],%s::integer[]) ON CONFLICT DO NOTHING'''


class HandoverProbeCase(unittest.TestCase):
    def test_only_the_real_api_phase_can_lock_and_insert_memberships(self):
        self.assertEqual(probe.admit_sql(INSERT, projection=True), 'insert')
        lock = 'LOCK TABLE hr_structure_salary_rule_rel IN SHARE ROW EXCLUSIVE MODE NOWAIT'
        self.assertEqual(probe.admit_sql(lock, projection=True), 'lock')
        row_lock = 'SELECT id FROM "hr_salary_rule" WHERE id=ANY(%s) ORDER BY id FOR UPDATE NOWAIT'
        self.assertEqual(probe.admit_sql(row_lock, projection=True), 'select')
        for sql in (INSERT, lock, row_lock):
            with self.subTest(sql=sql), self.assertRaises(probe.ProbeBlocked):
                probe.admit_sql(sql)
        for sql in (INSERT.replace('hr_structure_salary_rule_rel', 'hr_salary_rule'),
                    INSERT + ' RETURNING rule_id', INSERT.replace('DO NOTHING', 'DO UPDATE SET rule_id=1'),
                    'LOCK TABLE hr_salary_rule IN SHARE ROW EXCLUSIVE MODE NOWAIT'):
            with self.subTest(sql=sql), self.assertRaises(probe.ProbeBlocked):
                probe.admit_sql(sql, projection=True)

    def test_history_and_mutations_are_blocked_without_confusing_model_literals(self):
        safe = (
            "SELECT id FROM ir_model WHERE model='hr.payslip'",
            "SELECT 'hr_payslip' AS model_metadata FROM ir_model",
            'SELECT id FROM hr_payslip_input_type WHERE id=ANY(%s)',
            'SELECT * FROM hr_payroll_structure_hr_payslip_input_type_rel',
            'SAVEPOINT "1234abcdef"', 'ROLLBACK TO SAVEPOINT "1234abcdef"',
            'RELEASE SAVEPOINT "1234abcdef"', 'SHOW transaction_read_only',
        )
        for sql in safe:
            with self.subTest(sql=sql):
                probe.admit_sql(sql)
        forbidden = [f'SELECT id FROM "public"."{table}"' for table in probe.HISTORY_TABLES]
        forbidden += [
            'SELECT nextval(%s)', 'SELECT setval(%s,%s)', 'SELECT set_config(%s,%s,false)',
            'UPDATE hr_salary_rule SET active=true', 'DELETE FROM hr_structure_salary_rule_rel',
            'SELECT 1; SELECT 2', 'SELECT $$private body$$', 'COMMIT', 'ROLLBACK',
            'WITH x AS (DELETE FROM hr_salary_rule RETURNING id) SELECT * FROM x',
            'SELECT id FROM hr_salary_rule FOR UPDATE NOWAIT', 'SELECT 1 /* nested /* comment */',
        ]
        for sql in forbidden:
            with self.subTest(sql=sql), self.assertRaises(probe.ProbeBlocked):
                probe.admit_sql(sql)

    def test_cursor_observer_delegates_real_returns_and_restores_even_on_rejection(self):
        class Cursor:
            def __init__(self): self.calls = []
            def execute(self, sql, *args, **kwargs):
                self.calls.append((sql, args, kwargs))
                return 'unchanged-return'
        cursor = Cursor()
        original = Cursor.execute
        with probe.observe_cursor(cursor) as observation:
            self.assertEqual(cursor.execute('SELECT id FROM hr_salary_rule', [1]), 'unchanged-return')
            self.assertEqual(observation['statements'], 1)
            with self.assertRaises(probe.ProbeBlocked):
                Cursor().execute('SELECT 1')
            with self.assertRaises(probe.ProbeBlocked):
                cursor.execute('SELECT id FROM hr_payslip')
        self.assertIs(Cursor.execute, original)
        self.assertEqual(len(cursor.calls), 1)
        with self.assertRaises(probe.ProbeBlocked):
            with probe.observe_cursor(cursor):
                cursor.execute('DELETE FROM hr_salary_rule')
        self.assertIs(Cursor.execute, original)

    def test_primary_pairs_are_original_explicit_ids_not_inferred_defaults(self):
        rows = {'hr_payroll_structure': [{'id': i} for i in range(1, 5)],
            'hr_salary_rule': [{'id': i, 'struct_id': (i % 4) + 1} for i in range(1, 72)]}
        self.assertEqual(len(probe.expected_projection(rows)), 71)
        for alteration in ('missing', 'foreign', 'bool', 'duplicate', 'extra_structure'):
            changed = deepcopy(rows)
            if alteration == 'missing': changed['hr_salary_rule'][0]['struct_id'] = None
            elif alteration == 'foreign': changed['hr_salary_rule'][0]['struct_id'] = 19
            elif alteration == 'bool': changed['hr_salary_rule'][0]['struct_id'] = True
            elif alteration == 'duplicate': changed['hr_salary_rule'][1]['id'] = 1
            else: changed['hr_payroll_structure'].append({'id': 19})
            with self.subTest(alteration=alteration), self.assertRaises(probe.ProbeBlocked):
                probe.expected_projection(changed)

    def test_source88_and_reference3_are_distinct_and_noupdate_is_not_ignored(self):
        aliases = [dict(id=i, module='original', name='config_' + str(i), model='hr.salary.rule',
            res_id=i, noupdate=False) for i in range(1, 89)]
        report = dict(id=400, module='hr_payroll', name='action_report_payslip',
            model='ir.actions.report', res_id=462, noupdate=False)
        capsule = {'xmlids': aliases + [dict(id=500+i, module='reference', name='alias_'+str(i),
            model='hr.salary.rule', res_id=i, noupdate=False) for i in range(3)]}
        identity = {'original_xmlids': aliases + [report]}
        originals, reference, original_report = probe.source_alias_contract(capsule, identity)
        self.assertEqual((len(originals), len(reference), original_report['res_id']), (88, 3, 462))
        for field in ('id', 'model', 'res_id', 'noupdate'):
            changed = deepcopy(identity)
            changed['original_xmlids'][0][field] = 'changed'
            with self.subTest(field=field), self.assertRaises(probe.ProbeBlocked):
                probe.source_alias_contract(capsule, changed)
        with self.assertRaises(probe.ProbeBlocked):
            probe.source_alias_contract(capsule, {'original_xmlids': aliases})

    def test_full_report_baseline_is_required_before_authorized_write(self):
        alias = {'res_id': 462}
        row = dict(id=462, model='hr.payslip', type='ir.actions.report', report_type='qweb-pdf',
            write_uid=2, write_date='2026-10-29T00:00:00', report_name='hr_payroll.report_payslip_lang')
        baseline = {'original_report_462': {'table': 'ir_act_report_xml',
            'columns': list(row), 'rows_json': [json.dumps(row)]}}
        self.assertEqual(probe.report_contract(baseline, alias)[1], row)
        for alteration in ('absent', 'partial_columns', 'wrong_table', 'wrong_model', 'duplicate_row'):
            changed = deepcopy(baseline)
            if alteration == 'absent': changed = {}
            elif alteration == 'partial_columns': changed['original_report_462']['columns'].remove('write_date')
            elif alteration == 'wrong_table': changed['original_report_462']['table'] = 'ir_act_window'
            elif alteration == 'wrong_model':
                altered = dict(row, model='hr.employee')
                changed['original_report_462']['rows_json'] = [json.dumps(altered)]
            else: changed['original_report_462']['rows_json'] *= 2
            with self.subTest(alteration=alteration), self.assertRaises(probe.ProbeBlocked):
                probe.report_contract(changed, alias)

    def test_sealed_files_reject_wrong_hash_modes_symlinks_and_overwrite(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / 'source.json'
            source.write_text('{"private":"opaque"}')
            with patch.object(probe, 'PRIVATE_ROOT', root):
                with patch.object(probe.stat, 'S_IMODE', return_value=0o600):
                    self.assertEqual(probe.sealed_json(source, probe.sha(source.read_bytes())), {'private': 'opaque'})
                    with self.assertRaises(probe.ProbeBlocked):
                        probe.sealed_json(source, '0' * 64)
                with patch.object(probe.stat, 'S_IMODE', return_value=0o644):
                    with self.assertRaises(probe.ProbeBlocked):
                        probe.sealed_json(source, probe.sha(source.read_bytes()))
            output = root / 'proof.json'
            probe.write_receipt(output, {'passed': False})
            with self.assertRaises(FileExistsError):
                probe.write_receipt(output, {'passed': True})
            self.assertFalse(json.loads(output.read_text())['passed'])

    def test_database_guard_precedes_any_cursor_or_model_access(self):
        class Cursor:
            dbname = 'CERRO_EL_PLOMO'
            def execute(self, *args): raise AssertionError('must not execute')
        class Env:
            cr = Cursor()
            def __getitem__(self, name): raise AssertionError('must not load a model')
        with self.assertRaisesRegex(probe.ProbeBlocked, 'private-original-handover'):
            probe.run(Env(), None, probe.CAPSULE_SHA256, None, None, None)

    def test_real_access_error_message_goes_only_to_new_private_sidecar(self):
        AccessError = type('AccessError', (Exception,), {'__module__': 'odoo.exceptions'})
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder, 'proof.json')
            try:
                raise AccessError('synthetic-private-denied-record')
            except AccessError as error:
                receipt = probe.private_access_error(output, error)
            self.assertNotIn('synthetic-private-denied-record', json.dumps(receipt))
            self.assertFalse(receipt['exception_message_published'])
            path = Path(receipt['path'])
            self.assertIn('synthetic-private-denied-record', path.read_text())
            self.assertEqual(receipt['sha256'], probe.sha(path.read_bytes()))
            with self.assertRaises(FileExistsError):
                probe.private_access_error(output, AccessError('must-not-overwrite'))
            self.assertNotIn('must-not-overwrite', path.read_text())
            self.assertIsNone(probe.private_access_error(output, ValueError('ordinary-error')))

    def test_rejected_sql_is_still_denied_and_only_code_locations_are_captured(self):
        class Cursor:
            def __init__(self): self.executed = []
            def execute(self, query, *args, **kwargs):
                self.executed.append(query)
        cursor = Cursor()
        query = 'WITH RECURSIVE metadata AS (SELECT id FROM ir_ui_view) SELECT id FROM metadata'
        private_parameter = 'synthetic-private-parameter-not-for-capture'
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder, 'proof.json')
            captured = {}
            def rejected(code, error, projection):
                captured.update(probe.private_sql_rejection(output, code, error, projection))
            with self.assertRaisesRegex(probe.ProbeBlocked, 'non-projection-database-write-forbidden'):
                with probe.observe_cursor(cursor, rejected):
                    cursor.execute(query, [private_parameter])
            self.assertEqual(cursor.executed, [])
            self.assertEqual(captured['first_keyword'], 'WITH')
            self.assertFalse(captured['statement_executed'])
            self.assertNotIn(query, json.dumps(captured))
            private = Path(captured['path'])
            raw = private.read_bytes()
            self.assertEqual(captured['sha256'], probe.sha(raw))
            body = json.loads(raw)
            self.assertEqual(body['statement'], query)
            self.assertFalse(body['sql_parameters_captured'])
            self.assertFalse(body['source_lines_or_locals_captured'])
            self.assertNotIn(private_parameter, raw.decode())
            self.assertTrue(body['stack_frames'])
            self.assertTrue(all(set(frame) == {'file', 'line', 'function'} for frame in body['stack_frames']))
            with self.assertRaises(FileExistsError):
                probe.private_sql_rejection(output, query, probe.ProbeBlocked('still-denied'), False)

    def test_sql_capture_failure_cannot_cause_real_execution(self):
        class Cursor:
            def execute(self, *args): raise AssertionError('rejected query executed')
        def rejected(*args): raise OSError('private-capture-unavailable')
        # The run-level callback catches this and records a technical flag;
        # even an unexpected callback failure cannot reach the real cursor.
        cursor = Cursor()
        with self.assertRaises(OSError):
            with probe.observe_cursor(cursor, rejected):
                cursor.execute('WITH metadata AS (SELECT 1) SELECT * FROM metadata')


if __name__ == '__main__':
    unittest.main()
