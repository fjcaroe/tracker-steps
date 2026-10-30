"""Pure allowlist and startup-policy tests; no database or Odoo import."""
from pathlib import Path
import unittest

import original_external_references_runtime as runtime


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


if __name__ == '__main__':
    unittest.main()
