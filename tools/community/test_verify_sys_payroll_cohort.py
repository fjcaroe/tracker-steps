"""Pure sealed-custody replay negatives; no source DB or business operations."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

import capture_sys_payroll_cohort as capture
import verify_sys_payroll_cohort as verify


def bindings_fixture():
    tables = capture.CONFIG_TABLES + capture.CONFIG_RELATIONS + capture.PAYROLL_TABLES
    return {'schema': {name: [['id', 'integer', True]] for name in tables},
        'snapshots': {name: {'rows': 1, 'sha256': 'a'*64} for name in tables},
        'headers': [{'id': 1, 'contract_id': 2}], 'contract_provenance': [{'id': 2}],
        'lines': [{'id': 3, 'slip_id': 1, 'salary_rule_id': 9}],
        'worked_days': [{'id': 4, 'payslip_id': 1, 'type_id': 99, 'current_type_code': 'WORK100'}],
        'inputs': [{'id': 5, 'payslip_id': 1, 'type_id': 11, 'current_type_code': 'INPUT'}],
        'work_entries': [{'id': 6, 'contract_id': 2}], 'rules': [{'id': 9}],
        'configuration_keys': {'hr.salary.rule': [9], 'hr.payroll.structure': [1], 'hr.payroll.structure.type': [5],
            'hr.salary.rule.category': [8], 'hr.payslip.input.type': [11]}}


def reference_fixture():
    rows = [{'id': ident, 'slip_id': 1, 'salary_rule_id': ident, 'code': code, 'total': '0.00', 'write_date': '2026-09-30'}
        for ident, code in ((1, 'BASIC'), (2, 'GROSS'), (3, 'NET'))]
    case = {'id': 1, 'state': 'done', 'date_from': '2026-09-01', 'date_to': '2026-09-30', 'structure_id': 4,
        'concepts': {row['code']: [deepcopy(row)] for row in rows},
        'stored_totals': {'BASIC': '0.00', 'GROSS': '0.00', 'NET': '0.00'},
        'basis': {'contract_id': 2, 'worked_days': [], 'inputs': []}}
    payload = {'headers': [{'id': 1, 'state': 'done', 'date_from': '2026-09-01', 'date_to': '2026-09-30',
        'struct_id': 4, 'contract_id': 2}], 'lines': rows, 'worked_days': [], 'inputs': []}
    return payload, {'selected_case': case, 'ambiguous_concepts': []}


class SysCohortReplayCase(unittest.TestCase):
    def test_pinned_json_is_inert_and_changed_bytes_are_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'cohort.json'; raw = b'{"untrusted": "__import__(\\"os\\").system(\\"never\\")"}'
            path.write_bytes(raw)
            data, seen = verify.sealed_json(path, capture.sha(raw))
            self.assertEqual(seen, raw); self.assertIn('__import__', data['untrusted'])
            path.write_bytes(raw+b'\n')
            with self.assertRaises(capture.CaptureError): verify.sealed_json(path, capture.sha(raw))

    def test_twelve_complete_snapshots_and_actual_contract_bindings_are_replayed(self):
        result = verify.shape_and_bindings(bindings_fixture())
        self.assertEqual(result['snapshot_tables'], 12)
        self.assertTrue(result['payroll_children_bind_to_captured_header'])
        self.assertTrue(result['header_contracts_bind_to_actual_contract_rows'])
        self.assertTrue(result['work_entries_bind_to_selected_contracts'])
        self.assertFalse(result['direct_work_entry_payslip_link_proven'])
        self.assertFalse(result['work_entries_are_period_or_policy_approved'])
        self.assertFalse(result['foreign_key_constraints_introspected'])

    def test_missing_duplicate_and_foreign_parent_bindings_cannot_be_hidden(self):
        for change in ('table', 'schema', 'hash', 'header', 'line', 'contract', 'work_entry', 'rule', 'config_count'):
            data = bindings_fixture()
            if change == 'table': data['snapshots'].pop(capture.CONFIG_TABLES[0])
            if change == 'schema': data['schema'][capture.CONFIG_TABLES[0]] = []
            if change == 'hash': data['snapshots'][capture.CONFIG_TABLES[0]]['sha256'] = 'bad'
            if change == 'header': data['headers'].append(data['headers'][0])
            if change == 'line': data['lines'][0]['slip_id'] = 999
            if change == 'contract': data['contract_provenance'][0]['id'] = 999
            if change == 'work_entry': data['work_entries'][0]['contract_id'] = 999
            if change == 'rule': data['rules'].append(data['rules'][0])
            if change == 'config_count': data['configuration_keys']['hr.payslip.input.type'].append(22)
            with self.subTest(change=change), self.assertRaises(capture.CaptureError): verify.shape_and_bindings(data)

    def test_unresolved_rule_or_typed_endpoint_remains_explicit_not_backfilled(self):
        data = bindings_fixture(); data['lines'][0]['salary_rule_id'] = 999; data['inputs'][0]['current_type_code'] = None
        before = deepcopy(data); result = verify.shape_and_bindings(data)
        self.assertEqual({row['code'] for row in result['unresolved_endpoints']},
            {'CURRENT_RULE_ENDPOINT_MISSING', 'CURRENT_TYPED_ENDPOINT_MISSING'})
        self.assertEqual(data, before)

    def test_preserved_zero_and_positive_reference_require_all_original_rows(self):
        data, reference = reference_fixture()
        result = verify.reference_overlap(data, reference)
        self.assertTrue(result['selected_case_has_zero_essential_total'])
        self.assertTrue(result['stored_essential_line_identity_text_total_write_date_exact'])
        for change in ('amount', 'extra_essential', 'extra_day', 'extra_input', 'structure', 'contract', 'header'):
            bad = deepcopy(data)
            if change == 'amount': bad['lines'][0]['total'] = '-1'
            if change == 'extra_essential': bad['lines'].append(dict(bad['lines'][0], id=99))
            if change == 'extra_day': bad['worked_days'].append({'id': 99, 'payslip_id': 1})
            if change == 'extra_input': bad['inputs'].append({'id': 99, 'payslip_id': 1})
            if change == 'structure': bad['headers'][0]['struct_id'] = 99
            if change == 'contract': bad['headers'][0]['contract_id'] = 99
            if change == 'header': bad['headers'][0]['state'] = 'paid'
            result = verify.reference_overlap(bad, reference)
            keys = ('stored_essential_line_identity_text_total_write_date_exact', 'stored_worked_days_exact',
                    'stored_inputs_exact', 'selected_header_identity_exact')
            self.assertFalse(all(result[key] for key in keys), change)
            self.assertFalse(result['financial_certified'])

    def test_ambiguous_net_identity_and_zero_line_are_preserved_without_selection(self):
        data, reference = reference_fixture()
        data['lines'].append(dict(data['lines'][-1], id=4, salary_rule_id=8))
        reference['ambiguous_concepts'] = [{'slip_id': 1, 'code': 'NET', 'rule_ids': [3, 8], 'line_ids': [3, 4]}]
        result = verify.reference_overlap(data, reference)
        self.assertEqual(result['ambiguous_references'], [{'present': True, 'identities_exact': True,
            'line_ids_exact': True, 'zero_line_preserved': True}])
        self.assertFalse(result['stored_essential_line_identity_text_total_write_date_exact'])
        self.assertEqual(len(data['lines']), 4)


if __name__ == '__main__':
    unittest.main()
