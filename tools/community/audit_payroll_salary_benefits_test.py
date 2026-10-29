"""Read-only SQL transport and exposure boundaries; no benefit engine stand-in."""
import json
import unittest
from unittest.mock import patch

import audit_payroll_salary_benefits as audit


class BenefitAuditCase(unittest.TestCase):
    def test_sql_envelope_always_uses_readonly_repeatable_read_and_rollback(self):
        payload = audit.sql_payload({'test': 'SELECT 1 AS n'})
        self.assertTrue(payload.startswith('BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY;'))
        self.assertTrue(payload.endswith('ROLLBACK;'))
        self.assertNotIn('COMMIT;', payload)
        for statement in ('UPDATE x SET id=1', 'DELETE FROM x', 'ALTER TABLE x ADD id int', 'CREATE TABLE x(id int)'):
            with self.assertRaises(AssertionError): audit.sql_payload({'test': statement})

    def test_only_explicit_registered_references_can_be_read(self):
        for database in ('postgres', 'karo_consultorias', 'LAB_TAREAS', '', 'SyS; DELETE'):
            with patch.object(audit.subprocess, 'run', side_effect=AssertionError('Must not execute')) as invoked:
                with self.assertRaises(AssertionError): audit.snapshot(database, {})
                invoked.assert_not_called()

    def test_readonly_transport_requires_complete_mode_and_database_witness(self):
        queries = {'transaction': "SELECT 'witness'", 'test': 'SELECT 1 AS n'}
        valid = '\n'.join(json.dumps(row) for row in (
            {'section': 'transaction', 'rows': [{'database': 'SyS', 'read_only': 'on'}]},
            {'section': 'test', 'rows': [{'n': 1}]}))
        result = type('Result', (), {'stdout': valid})()
        with patch.object(audit.subprocess, 'run', return_value=result) as invoked:
            self.assertEqual(audit.snapshot('SyS', queries)['test'], [{'n': 1}])
            self.assertIn('PGOPTIONS=-c default_transaction_read_only=on', invoked.call_args.args[0])
            self.assertIn('READ ONLY', invoked.call_args.kwargs['input'])
        for changed in (valid.replace('"on"', '"off"'), valid.replace('"SyS"', '"OTHER"'), valid.splitlines()[0]):
            result.stdout = changed
            with patch.object(audit.subprocess, 'run', return_value=result):
                with self.assertRaises(AssertionError): audit.snapshot('SyS', queries)

    def test_usage_exports_hashes_counts_and_only_technical_contract_references(self):
        metadata = {'tables': [{'relname': 'hr_contract_salary_benefit'}], 'columns': [
            {'table_name': 'hr_contract_salary_benefit', 'column_name': name, 'data_type': kind}
            for name, kind in (('id', 'integer'), ('structure_type_id', 'integer'), ('field', 'character varying'), ('cost_field', 'text'))]}
        queries = audit.usage_queries(metadata)
        self.assertIn('sha256', queries['table:hr_contract_salary_benefit'])
        self.assertIn('count(*)', queries['table:hr_contract_salary_benefit'])
        self.assertIn("~ '^[a-z_][a-z0-9_]*$'", queries['contract-field-references:hr_contract_salary_benefit'])
        self.assertNotIn('SELECT *', audit.sql_payload(queries))
        self.assertNotIn('wage', audit.sql_payload(queries))
        self.assertIn('GROUP BY structure_type_id', queries['types:hr_contract_salary_benefit'])
        metadata['tables'] = [{'relname': 'hr_contract_salary_benefit; DROP TABLE x'}]
        with self.assertRaises(AssertionError): audit.usage_queries(metadata)

    def test_metadata_view_body_is_hashed_and_technical_identity_is_kept(self):
        queries = audit.metadata_queries()
        self.assertIn("encode(sha256(convert_to(arch_db::text,'UTF8'))", queries['views'])
        self.assertIn('noupdate', queries['xmlids'])
        self.assertIn('salary_benefits_ids', queries['fields'])
        self.assertNotIn('amount_python_compute', audit.sql_payload(queries))
        for name in ('hr_contract_salary_benefit;DROP', 'x.y', 'x"y', 'X'):
            with self.assertRaises(AssertionError): audit.identifier(name)


if __name__ == '__main__':
    unittest.main()
