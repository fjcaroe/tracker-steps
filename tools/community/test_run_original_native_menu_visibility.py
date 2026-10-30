"""Pure runner custody and startup tests, with no SSH, database or Odoo."""
import ast
from copy import deepcopy
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import run_original_native_menu_visibility as runner


def actor():
    return {'uid': 7, 'allowed_company_ids': [1, 2, 3, 4], 'active_company_id': 2,
        'original_company_memberships': [1, 2, 3, 4], 'superuser': False,
        'system_group_member': False, 'original_native_payroll_manager': True,
        'users_created': False, 'permissions_granted': False}


def source():
    return {'profile': 'source-native-original-master-id-visibility', 'database': runner.SOURCE_DATABASE,
        'actor': actor(), 'capsule_sha256': runner.CAPSULE_SHA256,
        'normal_actor_source_visibility_proven': True, 'database_writes': False, 'source_model_code_overridden': False}


def result_pair():
    menus = {'schema': 1, 'profile': 'source-native-original-menu-visibility', 'database': runner.SOURCE_DATABASE,
        'actor': actor(), 'source_visibility_sha256': runner.SOURCE_VISIBILITY_SHA256,
        'capsule_sha256': runner.CAPSULE_SHA256, 'identity_sha256': runner.IDENTITY_SHA256,
        'probe_sha256': sorted(runner.TOOL_HASHES['probe_original_menu_visibility.py'])[0], 'debug': False,
        'menus': {key: {'visible_debug_false': key != 'category'}
            for key in ('structure', 'rule', 'category', 'input_type')}}
    for key in ('database_writes', 'source_method_overridden', 'permissions_granted', 'actions_executed',
            'historical_payroll_read', 'salary_amounts_read', 'salary_rules_evaluated',
            'target_menu_equivalence_certified', 'identity_conversion', 'all_products_operational', 'deadline_resolved'):
        menus[key] = False
    cursor = {'database': runner.SOURCE_DATABASE, 'transaction_read_only': 'on', 'odoo_cursor_readonly': True}
    sequence = {'original_get_sequences_sha256': '6c41a6d4a995835a69a550420fbefb0987845008d8033035c96fea0670e5e000',
        'select_only_sql_sha256': '641394a53615d5d518b5e6f7c8ba4f867036d3ba66b848be7ce5789c001dc52b',
        'calls': [{**cursor, 'pg_is_in_recovery': False}], 'installed_sources_modified': False}
    sequence.update({key: True for key in ('cursor_readonly_unchanged', 'setup_signaling_unchanged',
        'signal_changes_unchanged', 'nextval_unchanged')})
    kernel = {'schema': 1, 'profile': 'source-native-menu-readonly-kernel', 'database': runner.SOURCE_DATABASE,
        'registry_entry': '/opt/odoo18/odoo-bin', 'source_model_method_overrides': False,
        'isolated_readonly_signaling_reader': True, 'database_writes': False,
        'startup_and_observation_readonly': True, 'cursors': [cursor], 'signaling_select_only': sequence}
    return menus, kernel


class NativeMenuRunnerCase(unittest.TestCase):
    def test_exact_original_source_actor_without_grants_is_the_only_selector(self):
        self.assertEqual(runner.explicit_actor(source()), actor())
        for key, value in (('database', 'CERRO_EL_PLOMO'), ('database_writes', True),
                ('normal_actor_source_visibility_proven', False), ('source_model_code_overridden', True)):
            altered = source(); altered[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError): runner.explicit_actor(altered)
        for key, value in (('superuser', True), ('system_group_member', True), ('permissions_granted', True),
                ('users_created', True), ('uid', 1), ('active_company_id', 99), ('allowed_company_ids', [1, 1])):
            altered = source(); altered['actor'][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError): runner.explicit_actor(altered)

    def test_official_readonly_bootstrap_command_has_no_upgrade_grant_or_alternate_actor(self):
        output = Path('/opt/steps-validation/community-native-menu-visibility-test')
        command = runner.native_command(runner.SOURCE_DATABASE, output, output / 'tools', '/official/addons')
        self.assertEqual(command[:5], ['sudo', '-u', 'cerro_odoo18', 'env', 'PYTHONDONTWRITEBYTECODE=1'])
        self.assertIn('/opt/odoo18/odoo-bin', command)
        self.assertIn('/etc/dev_odoo18.conf', command)
        self.assertIn('--db_host=/var/run/postgresql', command)
        self.assertIn('--no-http', command)
        self.assertIn('--max-cron-threads=0', command)
        self.assertFalse(set(command[5:]) & {'-u', '--update', '-i', '--init'})
        expression = runner.shell_expression(output, output / 'tools')
        ast.parse(expression)
        self.assertIn('source_visibility_sha256', expression)
        self.assertNotIn('actor_uid=', expression)
        self.assertNotIn('sudo(', expression)
        self.assertIn('_steps_readonly_cursor_proof', expression)
        with self.assertRaises(ValueError): runner.native_command('CERRO_EL_PLOMO', output, output / 'tools', '/addons')

    def test_pinned_helpers_match_actual_git_bytes_or_explicit_line_endings(self):
        for name, hashes in runner.TOOL_HASHES.items():
            raw = (Path(runner.__file__).parent / name).read_bytes()
            self.assertIn(runner.sha(raw), hashes, name)
        self.assertEqual(len(runner.TOOL_HASHES), 5)

    def test_new_private_copy_is_0600_from_creation_owned_and_never_overwrites(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); source_path = root / 'source'; source_path.write_bytes(b'sealed-json')
            owner = SimpleNamespace(pw_uid=1234, pw_gid=1234)
            destination = root / 'copy'
            original_open = os.open
            with patch.object(runner.os, 'chown', create=True) as chown, patch.object(runner.os, 'open', wraps=original_open) as opened:
                runner.private_copy(source_path, destination, runner.sha(b'sealed-json'), owner)
                self.assertEqual(destination.read_bytes(), b'sealed-json')
                opened.assert_called_once_with(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                chown.assert_called_once_with(destination, 1234, 1234)
                with self.assertRaises(FileExistsError): runner.private_copy(source_path, destination, runner.sha(b'sealed-json'), owner)
            with self.assertRaises(ValueError): runner.private_copy(source_path, root / 'wrong', '0' * 64, owner)

    def test_hidden_native_menu_is_recorded_but_readwrite_or_unproven_kernel_aborts(self):
        menus, kernel = result_pair()
        runner.validate_runtime_results(menus, kernel, actor())
        self.assertFalse(menus['menus']['category']['visible_debug_false'])
        for change in ('rw', 'no_cursors', 'foreign_db', 'grant', 'method', 'entry', 'sequence', 'nextval', 'no_calls'):
            actual_menu, actual_kernel = deepcopy(menus), deepcopy(kernel)
            if change == 'rw': actual_kernel['cursors'][0]['transaction_read_only'] = 'off'
            if change == 'no_cursors': actual_kernel['cursors'] = []
            if change == 'foreign_db': actual_kernel['cursors'][0]['database'] = 'CERRO_EL_PLOMO'
            if change == 'grant': actual_menu['permissions_granted'] = True
            if change == 'method': actual_menu['source_method_overridden'] = True
            if change == 'entry': actual_kernel['registry_entry'] = '/other/odoo-bin'
            if change == 'sequence': actual_kernel['signaling_select_only']['select_only_sql_sha256'] = '0' * 64
            if change == 'nextval': actual_kernel['signaling_select_only']['nextval_unchanged'] = False
            if change == 'no_calls': actual_kernel['signaling_select_only']['calls'] = []
            with self.subTest(change=change), self.assertRaises(ValueError):
                runner.validate_runtime_results(actual_menu, actual_kernel, actor())


if __name__ == '__main__':
    unittest.main()
