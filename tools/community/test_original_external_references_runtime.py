"""Pure allowlist and startup-policy tests; no database or Odoo import."""
from pathlib import Path
import unittest

import original_external_references_runtime as runtime
from original_external_references_readonly_bootstrap import enforce_readonly_pools, read_sequence_values, CACHE_KEYS, SEQUENCE_SELECT
from types import SimpleNamespace


class ExternalRegistryRuntimeCase(unittest.TestCase):
    def test_only_the_three_exact_accepted_profiles_are_admitted(self):
        for (root, mode), (database, count) in runtime.PROFILES.items():
            accepted = {'database': database, 'expected_test_count': count, 'mode': mode,
                'writes_to_source': False, 'source_files_sha256': 'a' * 64}
            self.assertEqual(runtime.authorize(Path(root), mode, accepted), database)
            for field, value in (('database', 'production'), ('expected_test_count', 0),
                    ('writes_to_source', True), ('source_files_sha256', 'missing')):
                with self.subTest(root=root, field=field), self.assertRaises(ValueError):
                    runtime.authorize(Path(root), mode, dict(accepted, **{field: value}))
            with self.assertRaises(ValueError):
                runtime.authorize(Path('other-root'), mode, accepted)

    def test_readonly_and_no_bytecode_policy_is_set_after_sudo_before_python_startup(self):
        original = ['sudo', '-u', 'private_role', '/usr/bin/python3.10', '/safe/odoo-bin', 'shell']
        result = runtime.readonly_command(original)
        self.assertEqual(result[:3], original[:3])
        self.assertEqual(result[3:6], ['env', 'PGOPTIONS=-c default_transaction_read_only=on',
            'PYTHONDONTWRITEBYTECODE=1'])
        self.assertEqual(result[6:], original[3:])
        self.assertEqual(original[3], '/usr/bin/python3.10')

    def test_real_pool_initialization_policy_cannot_be_added_after_a_connection_pool_exists(self):
        class Pool:
            def __init__(self, maxconn=64, readonly=False):
                self.readonly = readonly
                self._connections = []
        module = SimpleNamespace(_Pool=None, _Pool_readonly=None, ConnectionPool=Pool)
        enforce_readonly_pools(module)
        self.assertTrue(module.ConnectionPool(readonly=False).readonly)
        module._Pool = object()
        with self.assertRaises(ValueError):
            enforce_readonly_pools(module)

    def test_sequence_reader_requires_actual_readonly_local_primary_and_existing_values(self):
        class Cursor:
            readonly = True
            def __init__(self, rows):
                self.rows, self.queries = iter(rows), []
            def execute(self, query): self.queries.append(query)
            def fetchone(self): return next(self.rows)
        cursor = Cursor([('on',), (False,), (1, 2, 3, 4, 5, 6)])
        self.assertEqual(read_sequence_values(cursor, CACHE_KEYS), (1, dict(zip(CACHE_KEYS, (2, 3, 4, 5, 6)))))
        self.assertEqual(cursor.queries, ['SHOW transaction_read_only', 'SELECT pg_is_in_recovery()', SEQUENCE_SELECT])
        for rows in ([('off',)], [('on',), (True,)], [('on',), (False,), None], [('on',), (False,), (1,)]):
            with self.assertRaises(ValueError):
                read_sequence_values(Cursor(rows), CACHE_KEYS)
        for value in (False, None):
            cursor = Cursor([]); cursor.readonly = value
            with self.assertRaises(ValueError):
                read_sequence_values(cursor, CACHE_KEYS)
            self.assertFalse(cursor.queries)
        with self.assertRaises(ValueError):
            read_sequence_values(Cursor([]), tuple(reversed(CACHE_KEYS)))


if __name__ == '__main__':
    unittest.main()
