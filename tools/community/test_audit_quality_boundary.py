"""Pure admission tests for the native quality metadata reader."""
import json
import unittest
from unittest.mock import patch

import audit_quality_boundary as audit


class QualityBoundaryAuditCase(unittest.TestCase):
    def test_registered_private_copy_only_and_readonly_transaction(self):
        value = audit.payload(audit.DATABASE, audit.statements())
        self.assertTrue(value.startswith('BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY;'))
        self.assertTrue(value.endswith('ROLLBACK;'))
        for database in ('CERRO_EL_PLOMO', 'SyS', 'LAB_TAREAS', 'OTHER_PRIVATE'):
            with self.assertRaises(ValueError):
                audit.payload(database, audit.statements())

    def test_dml_multiple_statements_and_unsafe_section_names_are_refused(self):
        for name, value in (('bad', 'UPDATE quality_check SET quality_state=\'pass\''),
                ('bad', 'SELECT 1; DELETE FROM quality_check'), ('bad\'name', 'SELECT 1')):
            with self.assertRaises(ValueError):
                audit.payload(audit.DATABASE, {name: value})

    def test_snapshot_requires_every_section_and_proven_readonly_connection(self):
        rows = [{'section': 'transaction', 'rows': [{'database': audit.DATABASE, 'read_only': 'on'}]},
            {'section': 'models', 'rows': []}]
        queries = {'transaction': 'SELECT 1', 'models': 'SELECT 1'}
        with patch.object(audit.subprocess, 'check_output', return_value='\n'.join(map(json.dumps, rows))) as call:
            self.assertEqual(audit.snapshot(audit.DATABASE, queries)['models'], [])
            self.assertIn('PGOPTIONS=-c default_transaction_read_only=on', call.call_args.args[0])
        for altered in (rows[:1], rows + rows[1:], [{'section': 'transaction', 'rows': [{'database': audit.DATABASE, 'read_only': 'off'}]}, rows[1]]):
            with patch.object(audit.subprocess, 'check_output', return_value='\n'.join(map(json.dumps, altered))):
                with self.assertRaises(ValueError):
                    audit.snapshot(audit.DATABASE, queries)

    def test_queries_export_catalogue_and_hashes_without_native_source_bodies(self):
        value = '\n'.join(audit.statements().values())
        self.assertIn('architecture_sha256', value)
        self.assertNotIn('SELECT arch_db', value)
        self.assertNotIn('SELECT * FROM quality_check', value)
        self.assertNotIn('compute_sheet', value)


if __name__ == '__main__':
    unittest.main()
