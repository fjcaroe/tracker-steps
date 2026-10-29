"""Catalog transport and synthetic risk classification, without a database."""
import copy
from decimal import Decimal
import json
import unittest
from unittest.mock import patch

import audit_payroll_input_storage as audit


def fixture(native):
    columns = [{'attnum': 1, 'attname': 'amount', 'typname': 'numeric' if native else 'float8',
        'attnotnull': False, 'atthasdef': False, 'default_expression': None}]
    if not native:
        columns += [{'attnum': index, 'attname': name, 'typname': kind}
                    for index, (name, kind) in enumerate((('code', 'varchar'), ('contract_id', 'int4')), 2)]
    fields = [{'id': index + (100 if native else 200), 'model': audit.MODEL, 'name': name,
        'store': not native or name not in ('code', 'contract_id'),
        'related': {'code': 'input_type_id.code', 'contract_id': 'payslip_id.contract_id'}.get(name) if native else None}
        for index, name in enumerate(audit.FIELDS)]
    return {'columns': columns, 'fields': fields}


class InputStorageAuditCase(unittest.TestCase):
    def test_catalog_queries_never_select_business_rows_or_rule_source(self):
        payload = audit.sql_payload(audit.metadata_queries())
        self.assertTrue(payload.startswith('BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY;'))
        self.assertTrue(payload.endswith('ROLLBACK;'))
        for forbidden in ('FROM hr_payslip_input', 'FROM hr_payslip ', 'amount_python_compute',
                          'SELECT *', 'nextval(', 'setval(', 'COMMIT;'):
            self.assertNotIn(forbidden, payload)
        self.assertIn('pg_attribute', payload)
        self.assertIn('pg_get_constraintdef', payload)
        self.assertIn('pg_get_expr', payload)
        self.assertIn('noupdate', payload)
        for statement in ('UPDATE x SET id=1', 'SELECT 1; DELETE FROM x', 'ALTER TABLE x ADD y int'):
            with self.assertRaises(AssertionError):
                audit.sql_payload({'test': statement})

    def test_database_allowlist_precedes_any_sql_execution(self):
        for database in ('CERRO_EL_PLOMO', 'postgres', 'karo_consultorias', 'LAB_TAREAS', '', 'SyS; DROP'):
            with patch.object(audit.subprocess, 'run') as invoked:
                with self.assertRaises(AssertionError):
                    audit.snapshot(database)
                invoked.assert_not_called()

    def test_transport_requires_readonly_complete_unique_metadata_witness(self):
        data = {name: [] for name in audit.metadata_queries()}
        data.update(transaction=[{'database': 'SyS', 'read_only': 'on'}], table=[{'relname': 'hr_payslip_input'}],
                    model=[{'model': audit.MODEL}], fields=fixture(True)['fields'], columns=fixture(True)['columns'])
        lines = [json.dumps({'section': name, 'rows': rows}) for name, rows in data.items()]
        result = type('Result', (), {'stdout': '\n'.join(lines)})()
        with patch.object(audit.subprocess, 'run', return_value=result) as invoked:
            self.assertEqual(audit.snapshot('SyS'), data)
            self.assertIn('PGOPTIONS=-c default_transaction_read_only=on', invoked.call_args.args[0])
            self.assertIn('READ ONLY', invoked.call_args.kwargs['input'])
        for invalid in (result.stdout.replace('"on"', '"off"'), result.stdout.replace('"SyS"', '"OTHER"'),
                        '\n'.join(lines[:-1]), result.stdout + '\n' + lines[0]):
            result.stdout = invalid
            with patch.object(audit.subprocess, 'run', return_value=result), self.assertRaises(AssertionError):
                audit.snapshot('SyS')

    def test_related_metadata_never_invents_a_missing_column_and_no_conversion_is_authorized(self):
        source, target = fixture(True), fixture(False)
        plan = audit.classify(source, target)
        for name in ('code', 'contract_id'):
            self.assertIsNone(plan['fields'][name]['source_column'])
            self.assertTrue(plan['fields'][name]['related_to_stored'])
        self.assertTrue(plan['fields']['amount']['potential_precision_loss_if_converted'])
        self.assertFalse(plan['conversion_authorized'])
        self.assertFalse(plan['row_data_assessed'])
        self.assertFalse(plan['historical_materialization_certified'])
        self.assertIsNone(plan['ddl_or_dml_plan'])
        # A legacy physical column may coexist with store=False metadata.
        # Record its actual presence rather than asserting that it disappeared.
        source['columns'].append({'attname': 'code', 'typname': 'varchar'})
        self.assertIsNotNone(audit.classify(source, target)['fields']['code']['source_column'])

    def test_equal_storage_does_not_claim_observed_precision_loss(self):
        source = fixture(True)
        target = copy.deepcopy(source)
        target['columns'][0]['attnum'] += 4
        result = audit.classify(source, target)['fields']['amount']
        self.assertTrue(result['physical_contract_equal'])
        self.assertFalse(result['potential_precision_loss_if_converted'])
        self.assertFalse(result['row_loss_observed'])
        self.assertFalse(result['customer_value_projection_performed'])

    def test_identity_projection_keeps_only_available_safe_fields_and_refuses_conflicts(self):
        row = dict(fixture(False)['fields'][1], compute='DO NOT EXPORT SOURCE', name='code')
        partial = audit.identity_projection({'payroll_relations': {'fields': [row]}})
        self.assertEqual(set(partial), {'code'})
        self.assertNotIn('compute', partial['code'])
        self.assertNotIn('amount', partial)
        changed = dict(row, id=row['id'] + 1)
        with self.assertRaises(AssertionError):
            audit.identity_projection([row, changed])

    def test_synthetic_projection_distinguishes_null_zero_exact_decimal_precision_and_range(self):
        project = audit.synthetic_decimal_binary64_projection
        self.assertTrue(project(None)['sql_null_preserved'])
        for value in ('0', '-0', '0.5', '9007199254740992'):
            self.assertTrue(project(value)['numerically_exact'])
        self.assertTrue(project('-0')['negative_zero_preserved'])
        for value in ('0.1', '9007199254740993', '0.12345678901234567890123456789'):
            self.assertFalse(project(value)['numerically_exact'])
            self.assertEqual(project(value)['reason'], 'precision')
        self.assertEqual(project('1e99999')['reason'], 'overflow')
        self.assertEqual(project('1e-99999')['reason'], 'underflow')
        for value in ('NaN', 'Infinity', '-Infinity'):
            self.assertEqual(project(value)['reason'], 'nonfinite')
        with self.assertRaises(ValueError):
            project(False)
        self.assertTrue(project(Decimal('0.25'))['synthetic_only'])


if __name__ == '__main__':
    unittest.main()
