"""Boundary tests with actual command inspection; never connects PostgreSQL."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
from types import ModuleType
import unittest
from unittest.mock import patch

import original_anchor_readonly_sql as readonly


DATABASE = 'MANAGEMENT_QA_CERRO_PAYROLL_API_ORIGINAL_HANDOVER_TEST'
REFERENCE = DATABASE.replace('_HANDOVER_', '_REFERENCE_')


class ReadonlyReviewCase(unittest.TestCase):
    def response(self, command, *, input, **kwargs):
        database = next(value.split('=', 1)[1] for value in command if value.startswith('--dbname='))
        output = json.dumps({'database': database, 'transaction_read_only': 'on',
            'default_transaction_read_only': 'on'}) if input == readonly.SETTING_QUERY else 'real-unchanged-result\n'
        return subprocess.CompletedProcess(command, 0, output, '')

    def test_environment_is_cleaned_after_sudo_and_actual_readonly_is_proven(self):
        executor = readonly.ReadOnlyReviewSQL(DATABASE, REFERENCE)
        original = "SET jit=off; SELECT md5(E'\\n') FROM ir_model"
        with patch.object(readonly.subprocess, 'run', side_effect=self.response) as run:
            self.assertEqual(executor(DATABASE, original), 'real-unchanged-result')
            executor(REFERENCE, 'SELECT 1')
            executor(DATABASE, 'SELECT 2')
        self.assertEqual(run.call_count, 5)  # 2 real setting queries + 3 delegated.
        for call in run.call_args_list:
            command = call.args[0]
            self.assertEqual(command[:7], ['/usr/bin/sudo', '-n', '-u', 'postgres', '/usr/bin/env', '-i',
                'PATH=/usr/bin:/bin'])
            self.assertIn('PGOPTIONS=-c default_transaction_read_only=on', command)
            self.assertIn('PGPASSFILE=/dev/null', command)
            self.assertIn('PGSERVICEFILE=/dev/null', command)
            self.assertIn('HOME=/nonexistent', command)
            self.assertIn('PGHOST=/var/run/postgresql', command)
            self.assertIn('-X', command)
            self.assertIn('--no-password', command)
            self.assertFalse(any('PGPASSWORD' in value for value in command))
        self.assertEqual(run.call_args_list[1].kwargs['input'], original)
        proof = executor.proof()
        self.assertEqual(proof['query_count'], 3)
        self.assertTrue(proof['original_queries_delegated_unmodified'])
        self.assertFalse(proof['query_results_rewritten'])

    def test_wrong_database_nonreadonly_setting_and_commands_reject_before_delegation(self):
        for database, reference in (('CERRO_EL_PLOMO', REFERENCE), (DATABASE, 'another_database')):
            with self.assertRaises(ValueError): readonly.ReadOnlyReviewSQL(database, reference)
        with self.assertRaises(ValueError): readonly.command('CERRO_EL_PLOMO')
        executor = readonly.ReadOnlyReviewSQL(DATABASE, REFERENCE)
        with patch.object(readonly.subprocess, 'run') as run:
            for statement in ('UPDATE ir_model SET model=%s', 'SELECT 1; COMMIT',
                'SET default_transaction_read_only=off; SELECT 1', 'SELECT set_config(%s,%s,false)',
                'SELECT nextval(%s)', 'SELECT * FROM dblink(%s)'):
                with self.subTest(statement=statement), self.assertRaises(ValueError):
                    executor(DATABASE, statement)
            with self.assertRaises(ValueError): executor('CERRO_EL_PLOMO', 'SELECT 1')
            run.assert_not_called()
        result = subprocess.CompletedProcess([], 0, json.dumps({'database': DATABASE,
            'transaction_read_only': 'off', 'default_transaction_read_only': 'on'}), '')
        with patch.object(readonly.subprocess, 'run', return_value=result) as run:
            with self.assertRaisesRegex(ValueError, 'setting-not-proven'): executor(DATABASE, 'SELECT 1')
            self.assertEqual(run.call_count, 1)
        failed = subprocess.CompletedProcess([], 1, '', 'PRIVATE SOURCE VALUE MUST NOT LEAK')
        with patch.object(readonly.subprocess, 'run', return_value=failed):
            with self.assertRaisesRegex(ValueError, '^readonly-postgresql-review-query-rejected$'):
                executor(DATABASE, 'SELECT 1')

    def test_reviewer_binds_all_real_helper_globals_and_restores_on_failure(self):
        fake = {}
        for name in ('run_original_anchor', 'validate_agriculture_core', 'validate_community_reports',
                     'payroll_configuration_adoption_preflight'):
            module = ModuleType(name)
            module.sql = object()
            fake[name] = module
        fake['run_original_anchor'].column_snapshot = object()
        fake['run_original_anchor'].original_columns = object()
        path = Path(__file__).with_name('review_original_anchor.py')
        spec = importlib.util.spec_from_file_location('review_test_isolated', path)
        module = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, fake):
            spec.loader.exec_module(module)
        original = {name: value.sql for name, value in fake.items()}
        executor = object()
        with self.assertRaisesRegex(ValueError, 'synthetic boundary'):
            with module.readonly_bindings(executor):
                self.assertIs(module.sql, executor)
                for name in ('run_original_anchor', 'validate_agriculture_core', 'validate_community_reports'):
                    self.assertIs(fake[name].sql, executor)
                raise ValueError('synthetic boundary')
        for name in original:
            self.assertIs(fake[name].sql, original[name])
        self.assertIs(module.sql, original['validate_community_reports'])


if __name__ == '__main__':
    unittest.main()
