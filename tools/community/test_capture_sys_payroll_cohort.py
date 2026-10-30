"""Pure custody/identity negatives; no database, Odoo or real financial data."""
from copy import deepcopy
from datetime import date
import json
from pathlib import Path
import tempfile
import unittest

import capture_sys_payroll_cohort as capture


def rule(ident):
    return {'id': ident, 'code': 'R%s' % ident, 'active': True, 'sequence': ident,
        'amount_select': 'code', 'condition_select': 'none', 'amount_fix': 0,
        'amount_percentage': 0, 'condition_range_min': 0, 'condition_range_max': 0,
        'not_computed_in_net': False, 'split_move_lines': False, 'appears_on_payslip': True,
        'category_id': 1, 'struct_id': 1, 'condition_other_input_id': None,
        'amount_other_input_id': None, 'amount_python_compute': 'result = 0',
        'condition_python': None, 'condition_range': None, 'quantity': '1.0',
        'amount_percentage_base': None}


def matrix_fixture():
    rows = [rule(ident) for ident in range(1, 72)]
    aliases = [{'id': row['id'], 'module': 'original', 'name': 'rule_%s' % row['id'],
        'model': 'hr.salary.rule', 'res_id': row['id'], 'noupdate': True} for row in rows]
    aliases += [{'id': 100, 'module': 'original', 'name': 'category', 'model': 'hr.salary.rule.category', 'res_id': 1},
        {'id': 101, 'module': 'original', 'name': 'structure', 'model': 'hr.payroll.structure', 'res_id': 1}]
    capsule = {'tables': {'hr_salary_rule': {'row_count': 71, 'rows_json': [json.dumps(row) for row in rows]}}, 'xmlids': aliases}
    current = [{'id': row['id'], 'values': {key: str(row[key]) if key in capture.NUMERIC_RULE_VALUES else row[key]
        for key in capture.RULE_VALUES}, 'references': {key: row[key] for key in capture.RULE_REFERENCES},
        'expressions': {key: capture.expression(row[key]) for key in capture.EXPRESSION_FIELDS}} for row in rows]
    payload = {'aliases': deepcopy(aliases), 'rules': current,
        'lines': [{'id': row['id'], 'slip_id': 1, 'salary_rule_id': row['id']} for row in rows]}
    return capsule, payload


def payload_fixture():
    return {'metadata': {'database': 'SyS', 'transaction_read_only': 'on', 'default_transaction_read_only': 'on',
        'isolation': 'repeatable read', 'in_recovery': False, 'as_of': '2026-10-30'},
        'pending': [], 'providers': [{'name': name, 'state': 'installed', 'license': license, 'version': '18.0.1.0.0'}
            for name, license in (('hr_payroll', 'OEEL-1'), ('hr_payroll_account', 'OEEL-1'),
                                  ('l10n_cl_simpledigital_payroll', 'AGPL-3'))],
        'schema': dict.fromkeys(capture.CONFIG_TABLES + capture.CONFIG_RELATIONS + capture.PAYROLL_TABLES, []),
        'snapshots': dict.fromkeys(capture.CONFIG_TABLES + capture.CONFIG_RELATIONS + capture.PAYROLL_TABLES, {}),
        'closed_population': {'all_closed': 1, 'previous_months': 1},
        'headers': [{'id': 1, 'state': 'done', 'date_from': '2026-09-01', 'date_to': '2026-09-30'}],
        'lines': [{'id': ident, 'slip_id': 1, 'salary_rule_id': ident, 'code': code,
            'amount': '0.000', 'quantity': '1', 'rate': '100', 'total': '0.000'}
            for ident, code in ((1, 'BASIC'), (2, 'GROSS'), (3, 'NET'))],
        'worked_days': [], 'inputs': []}


class SysCohortCaptureCase(unittest.TestCase):
    def test_single_readonly_snapshot_has_no_names_formulas_writes_or_recomputation(self):
        sql = capture.sql_capture('2026-10-30')
        self.assertEqual(sql.count('BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY;'), 1)
        self.assertTrue(sql.rstrip().endswith('ROLLBACK;'))
        self.assertEqual(sql.count('ROLLBACK;'), 1)
        for mutation in ('UPDATE ', 'INSERT ', 'DELETE ', 'CREATE ', 'ALTER ', 'nextval(', 'compute_sheet'):
            self.assertNotIn(mutation, sql)
        self.assertIn("'amount',l.amount::text", sql)
        self.assertIn("'quantity',l.quantity::text", sql)
        self.assertIn("'rate',l.rate::text", sql)
        self.assertIn("'total',l.total::text", sql)
        self.assertNotIn("'employee_id'", sql)
        self.assertNotRegex(sql, r"'name',(s|c|l|w|i|e)\.name")
        with self.assertRaises(ValueError): capture.sql_capture("2026-10-30'; DELETE FROM hr_payslip; --")

    def test_canonical_registry_resolves_exact_sys_without_returning_password(self):
        registry = {'instance': 'odoo-new', 'environments': {'sys': {'role': 'production', 'database': 'SyS',
            'config': '/etc/odoo18-sys.conf'}}}
        result = capture.resolve_source(registry, lambda path: {'db_name': 'SyS', 'addons_path': '/first,/second',
            'db_password': 'synthetic-never-export'})
        self.assertEqual(result, ('SyS', '/etc/odoo18-sys.conf', (Path('/first'), Path('/second'))))
        self.assertNotIn('synthetic-never-export', str(result))
        for change in ({'role': 'qa'}, {'database': 'STEPS_DEMO_SYS'}, {'config': '/etc/demo.conf'}):
            bad = deepcopy(registry); bad['environments']['sys'].update(change)
            with self.assertRaises(capture.CaptureError): capture.resolve_source(bad, lambda p: {})
        with self.assertRaises(capture.CaptureError): capture.resolve_source(registry,
            lambda p: {'db_name': 'other', 'addons_path': '/first'})

    def test_pending_operations_and_runtime_provider_mismatch_are_fail_closed(self):
        payload = payload_fixture()
        self.assertEqual(capture.validate_payload(payload, {'version': '18.0.1.0.0'}), [])
        for change in ('pending', 'rw', 'replica', 'isolation', 'version', 'schema', 'duplicate', 'open', 'current'):
            bad = deepcopy(payload)
            if change == 'pending': bad['pending'] = [{'name': 'module', 'state': 'to upgrade'}]
            if change == 'rw': bad['metadata']['transaction_read_only'] = 'off'
            if change == 'replica': bad['metadata']['in_recovery'] = True
            if change == 'isolation': bad['metadata']['isolation'] = 'read committed'
            if change == 'version': bad['providers'][-1]['version'] = '18.0.2.0.0'
            if change == 'schema': bad['schema'].pop(capture.CONFIG_TABLES[0])
            if change == 'duplicate': bad['lines'].append(bad['lines'][0])
            if change == 'open': bad['headers'][0]['state'] = 'draft'
            if change == 'current': bad['headers'][0]['date_to'] = '2026-10-01'
            with self.subTest(change=change), self.assertRaises(capture.CaptureError):
                capture.validate_payload(bad, {'version': '18.0.1.0.0'})

    def test_null_and_nonfinite_components_are_preserved_as_issues_never_reconstructed(self):
        for value in (None, 'NaN', 'Infinity', '-Infinity', 0.0):
            payload = payload_fixture(); payload['lines'][0]['amount'] = value
            before = deepcopy(payload)
            issues = capture.validate_payload(payload, {'version': '18.0.1.0.0'})
            self.assertTrue(any(row['code'] == 'STORED_COMPONENT_NULL_OR_NONFINITE' for row in issues))
            self.assertEqual(payload, before)
        payload = payload_fixture(); payload['lines'][0].update(amount='-0.005000', quantity='3', rate='100', total='-0.02')
        self.assertEqual(capture.validate_payload(payload, {'version': '18.0.1.0.0'}), [])
        self.assertEqual(payload['lines'][0]['amount'], '-0.005000')

    def test_zero_net_of_second_identity_remains_ambiguous_without_choosing_rule(self):
        payload = payload_fixture()
        payload['lines'].append(dict(payload['lines'][-1], id=4, salary_rule_id=8, total='0'))
        issues = capture.validate_payload(payload, {'version': '18.0.1.0.0'})
        uncertain = [row for row in issues if row['code'] == 'ESSENTIAL_RULE_IDENTITY_AMBIGUOUS']
        self.assertEqual(len(uncertain), 1); self.assertEqual(uncertain[0]['rule_ids'], [3, 8])
        self.assertEqual(len(payload['lines']), 4)

    def test_same_original_xmlid_requires_actual_endpoints_not_same_id_or_code(self):
        capsule, payload = matrix_fixture()
        matrix = capture.compare_rules(capsule, payload)
        self.assertEqual(len(matrix), 71)
        self.assertTrue(all(row['binding'] == 'same_original_xmlid' and not row['current_differences'] for row in matrix))
        self.assertTrue(all('HISTORICAL_CONFIGURATION_TIMELINE_UNPROVEN' in row['blockers']
            and row['financial_equivalence_certified'] is False for row in matrix))
        payload['aliases'] = [r for r in payload['aliases'] if not (r['model'] == 'hr.salary.rule' and r['res_id'] == 1)]
        first = capture.compare_rules(capsule, payload)[0]
        self.assertIsNone(first['sys_rule_id']); self.assertEqual(first['stored_line_ids'], [])
        self.assertIn('ORIGINAL_RULE_IDENTITY_UNPROVEN', first['blockers'])

    def test_changed_formula_null_and_reference_identity_block_current_equivalence(self):
        capsule, payload = matrix_fixture()
        payload['rules'][0]['expressions']['amount_python_compute'] = capture.expression('result = 1')
        payload['rules'][0]['expressions']['condition_python'] = capture.expression('')
        payload['rules'][0]['references']['category_id'] = 999
        first = capture.compare_rules(capsule, payload)[0]
        self.assertEqual(set(first['current_differences']), {'amount_python_compute_sha256', 'condition_python_sha256', 'category_id_identity'})
        self.assertIn('CURRENT_CONFIGURATION_DIFFERS', first['blockers'])

    def test_conflicting_aliases_and_uncovered_rules_never_infer_ownership(self):
        capsule, payload = matrix_fixture()
        payload['aliases'].append({'module': 'original', 'name': 'rule_1', 'model': 'hr.salary.rule', 'res_id': 2})
        first = capture.compare_rules(capsule, payload)[0]
        self.assertIn('ORIGINAL_RULE_IDENTITY_AMBIGUOUS', first['blockers'])
        payload['lines'] = []
        self.assertTrue(all('NO_STORED_RULE_COVERAGE' in row['blockers'] for row in capture.compare_rules(capsule, payload)))
        capsule['tables']['hr_salary_rule']['rows_json'].pop()
        with self.assertRaises(capture.CaptureError): capture.compare_rules(capsule, payload)

    def test_two_original_rules_cannot_be_certified_as_one_target_identity(self):
        capsule, payload = matrix_fixture()
        next(row for row in payload['aliases'] if row['model'] == 'hr.salary.rule' and row['res_id'] == 2)['res_id'] = 1
        matrix = capture.compare_rules(capsule, payload)
        for row in matrix[:2]:
            self.assertIsNone(row['binding'])
            self.assertIn('ORIGINAL_RULE_NAMESPACE_MERGED', row['blockers'])
            self.assertFalse(row['financial_equivalence_certified'])

    def test_decimal_configuration_values_keep_precision_without_float_coercion(self):
        capsule, payload = matrix_fixture()
        row = json.loads(capsule['tables']['hr_salary_rule']['rows_json'][0]); row['amount_fix'] = '12345678901234567890.123456789000'
        capsule['tables']['hr_salary_rule']['rows_json'][0] = json.dumps(row)
        payload['rules'][0]['values']['amount_fix'] = '12345678901234567890.123456789'
        self.assertNotIn('amount_fix', capture.compare_rules(capsule, payload)[0]['current_differences'])
        payload['rules'][0]['values']['amount_fix'] = '12345678901234567890.123456788'
        self.assertIn('amount_fix', capture.compare_rules(capsule, payload)[0]['current_differences'])

    def test_provider_license_pin_and_changed_file_abort_before_sql(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); provider = root / 'l10n_cl_simpledigital_payroll'; provider.mkdir()
            manifest = repr({'license': 'AGPL-3', 'version': '18.0.1.0.0'}).encode()
            (provider / '__manifest__.py').write_bytes(manifest)
            (provider / 'model.py').write_bytes(b'# synthetic public fixture\n')
            pin = {'license': 'AGPL-3', 'version': '18.0.1.0.0', 'files': {
                name: capture.sha((provider / name).read_bytes()) for name in ('__manifest__.py', 'model.py')}}
            self.assertEqual(capture.provider_snapshot((root,), pin)['files'], pin['files'])
            (provider / 'model.py').write_bytes(b'# drift\n')
            with self.assertRaises(capture.CaptureError): capture.provider_snapshot((root,), pin)


if __name__ == '__main__':
    unittest.main()
