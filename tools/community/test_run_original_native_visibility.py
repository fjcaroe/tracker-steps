"""Pure Source graph runner opt-in and custody tests, never an Odoo launch."""
import ast
import os
from pathlib import Path, PurePosixPath
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import run_original_native_visibility as runner
from test_source_graph_visibility import graph_fixture, pinned_fixture


class NativeVisibilityRunnerCase(unittest.TestCase):
    def test_default_expression_is_legacy381_and_inventory_is_the_only_graph_opt_in(self):
        actor = {'uid': 7, 'allowed_company_ids': [1, 2, 3, 4], 'active_company_id': 2}
        output = PurePosixPath('/opt/steps-validation/community-native-visibility-unit')
        arguments = (output / 'tools', output / 'capsule.json', 'a' * 64, actor, output)
        legacy = runner.observation_expression(*arguments)
        opted = runner.observation_expression(*arguments, output / 'source-inventory.json')
        ast.parse(legacy); ast.parse(opted)
        self.assertNotIn('source_inventory_path', legacy)
        self.assertIn("source_inventory_path='/opt/steps-validation/community-native-visibility-unit/source-inventory.json'", opted)
        for expression in (legacy, opted):
            self.assertIn('actor_uid=7', expression)
            self.assertIn('active_company_id=2', expression)
            self.assertNotIn('sudo(', expression)
            self.assertNotIn('has_group', expression)

    def test_opt_in_copies_exact_sealed_inventory_0600_owned_and_never_overwrites(self):
        modules, raw = graph_fixture()
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary); original = output / 'inventory.json'; original.write_bytes(raw)
            owner = SimpleNamespace(pw_uid=1234, pw_gid=1234)
            actual_open = os.open
            # Path custody is Linux-specific. The pure test substitutes only
            # the fixed private root check; hash/projection/copy are real.
            with pinned_fixture(modules, raw), patch.object(runner.Path, 'is_relative_to', return_value=True), \
                    patch.object(runner.os, 'chown', create=True) as chown, patch.object(runner.os, 'open', wraps=actual_open) as opened:
                destination = runner.copy_source_inventory(original, output, owner)
                self.assertEqual(destination.read_bytes(), raw)
                opened.assert_called_once_with(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                chown.assert_called_once_with(destination, 1234, 1234)
                with self.assertRaises(FileExistsError): runner.copy_source_inventory(original, output, owner)
            original.write_bytes(raw + b' ')
            with patch.object(runner.Path, 'is_relative_to', return_value=True), self.assertRaises(ValueError):
                runner.copy_source_inventory(original, output, owner)

    def test_runner_keeps_official_readonly_bootstrap_offline_lease_and_has_no_actor_grant_flags(self):
        source = Path(runner.__file__).read_text(encoding='utf-8-sig')
        self.assertIn("parser.add_argument('--source-inventory'", source)
        self.assertNotIn("parser.add_argument('--actor", source)
        self.assertNotIn("parser.add_argument('--group", source)
        self.assertIn('original_external_references_readonly_bootstrap.py', source)
        self.assertIn('/opt/odoo18/odoo-bin', source)
        self.assertIn('/run/lock/steps-environments.lock', source)
        self.assertIn('offline_odoo(command)', source)
        tree = ast.parse(source)
        methods = {node.func.attr for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)}
        self.assertFalse(methods & {'execute', 'db_connect', 'sudo', 'compute_sheet'})


if __name__ == '__main__':
    unittest.main()
