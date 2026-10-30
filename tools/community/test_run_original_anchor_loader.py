import ast
import copy
import hashlib
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

import run_original_anchor_loader as loader


class Cursor:
    def __init__(self, rows):
        self.rows = list(rows)

    def execute(self, sql, params=None):
        if not sql.startswith('SELECT '): raise AssertionError('Only guard metadata SELECT is admitted')

    def fetchall(self):
        return self.rows.pop(0)


class OriginalAnchorLoaderCase(unittest.TestCase):
    database = 'MANAGEMENT_QA_CERRO_PAYROLL_API_ORIGINAL_HANDOVER_TEST'

    def argv(self):
        return ['-c', '/private/config', '-d', self.database, '--db-filter=^' + self.database + '$',
            '--workers=0', '--max-cron-threads=0', '--without-demo=all', '--stop-after-init',
            '--no-http', '-i', 'payroll,step_simpledigital_oca_base']

    def guards(self):
        rows = [(table, trigger, 'O', event, 'step_anchor_guard_' + table, 'a' * 32)
                for table in loader.TABLES for trigger, event in (
                    ('step_anchor_preserve_original_row', 27), ('step_anchor_preserve_original_truncate', 34))]
        rows.append(('res_groups_report_rel', 'step_anchor_preserve_original_insert', 'O', 7,
                     'step_anchor_guard_res_groups_report_rel', 'b' * 32))
        return sorted(rows)

    def test_parameters_keep_wrapper_and_real_cli_scopes_separate(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            own = ['--runtime', str(root), '--database', self.database, '--capsule', str(root / 'capsule'),
                '--capsule-sha256', loader.retention.CAPSULE_SHA256, '--identity-before', str(root / 'identity'),
                '--identity-before-sha256', 'c' * 64, '--receipt', str(root / 'receipt.json')]
            with patch.object(loader, 'PRIVATE_ROOT', root):
                options, args = loader.parse_arguments(own + ['--'] + self.argv())
                self.assertEqual(options.database, self.database)
                self.assertEqual(args, self.argv())
                with self.assertRaisesRegex(ValueError, 'separator'):
                    loader.parse_arguments(own + self.argv())
                (root / 'receipt.json').touch()
                with self.assertRaisesRegex(ValueError, 'receipt'):
                    loader.parse_arguments(own + ['--'] + self.argv())

    def test_cli_rejects_other_database_duplicates_server_or_tests_modes(self):
        for mode in ('other-db', 'duplicate-db', 'attached-db', 'abbreviated-db', 'abbreviated-workers',
                     'workers', 'cron', 'demo', 'http', 'no-stop', 'no-install', 'test', 'shell', 'password', 'short-password'):
            args = self.argv()
            if mode == 'other-db': args[3] = 'CERROELPLOMO'
            elif mode == 'duplicate-db': args += ['--database=' + self.database]
            elif mode == 'attached-db': args += ['-dCERROELPLOMO']
            elif mode == 'abbreviated-db': args += ['--databas=CERROELPLOMO']
            elif mode == 'abbreviated-workers': args += ['--work=2']
            elif mode in ('workers', 'cron', 'demo'):
                index = {'workers': 5, 'cron': 6, 'demo': 7}[mode]
                args[index] = {'workers': '--workers=2', 'cron': '--max-cron-threads=1', 'demo': '--without-demo='}[mode]
            elif mode == 'http': args.remove('--no-http')
            elif mode == 'no-stop': args.remove('--stop-after-init')
            elif mode == 'no-install': args = args[:-2]
            elif mode == 'test': args += ['--test-enable']
            elif mode == 'shell': args = ['shell'] + args
            elif mode == 'password': args += ['--db_password=never-log-this']
            elif mode == 'short-password': args += ['-wnever-log-this']
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                loader.validate_odoo_arguments(args, self.database)

    def test_source_is_bound_to_clean_official_git_and_exact_method_body(self):
        raw = b'class IrModelData:\n    def _process_end(self, modules):\n        return modules\n'
        method = ast.parse(raw.decode()).body[0].body[0]
        method_hash = hashlib.sha256(ast.get_source_segment(raw.decode(), method).encode()).hexdigest()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / loader.MODEL_FILE
            source.parent.mkdir(parents=True)
            source.write_bytes(raw)
            with patch.object(loader, 'MODEL_SHA256', hashlib.sha256(raw).hexdigest()), \
                    patch.object(loader, 'METHOD_SHA256', method_hash), \
                    patch.object(loader.subprocess, 'check_output', side_effect=[loader.PIN + '\n', '', raw]):
                proof = loader.validate_runtime(root)
                self.assertEqual(proof['official_pin'], loader.PIN)
            for observations in (['wrong\n'], [loader.PIN + '\n', ' M source\n'], [loader.PIN + '\n', '', b'other']):
                with patch.object(loader.subprocess, 'check_output', side_effect=observations), self.assertRaises(ValueError):
                    loader.validate_runtime(root)

    def test_every_guard_must_exist_be_active_and_have_exact_event_and_owner(self):
        proof = loader.check_database_guards(Cursor([[('origin',)], self.guards()]))
        self.assertEqual(len(proof), 23)
        for variant in ('missing', 'disabled', 'wrong-events', 'wrong-function', 'duplicate'):
            rows = self.guards()
            if variant == 'missing': rows.pop()
            else:
                row = list(rows[0])
                if variant == 'disabled': row[2] = 'D'
                elif variant == 'wrong-events': row[3] = 7
                elif variant == 'wrong-function': row[4] = 'other_guard'
                elif variant == 'duplicate': rows[-1] = rows[0]
                rows[0] = tuple(row)
            with self.subTest(variant=variant), self.assertRaises(ValueError):
                loader.check_database_guards(Cursor([[('origin',)], rows]))
        with self.assertRaisesRegex(ValueError, 'not-origin'):
            loader.check_database_guards(Cursor([[('replica',)]]))

    def wrapper(self, original):
        original._api = 'model'
        cls = type('IrModelData', (), {'_process_end': original})
        module = SimpleNamespace(IrModelData=cls)
        options = SimpleNamespace(runtime=Path('/official/runtime'), database=self.database,
            capsule=Path('/private/capsule'), capsule_sha256=loader.retention.CAPSULE_SHA256,
            identity_before=Path('/private/identity'), identity_before_sha256='c' * 64)
        calls = []
        with patch.object(loader.inspect, 'getsourcefile', return_value=str(options.runtime / loader.MODEL_FILE)):
            loader.install_wrapper(module, options, calls)
        env = SimpleNamespace(cr=SimpleNamespace(dbname=self.database),
            registry=SimpleNamespace(loaded_xmlids={'base.existing'}))
        return cls, SimpleNamespace(env=env), calls

    def test_retains_only_after_guards_then_delegates_original_and_preserves_return(self):
        events = []
        result = object()
        def original(self, modules):
            events.append('original')
            self.env.registry.loaded_xmlids.clear()
            return result
        cls, record, calls = self.wrapper(original)
        def retain(env, **kwargs):
            events.append('retain')
            env.registry.loaded_xmlids.update({'exact.alias.1', 'exact.alias.2'})
            return {'exact_two_aliases_retained': True}
        with patch.object(loader, 'check_database_guards', side_effect=lambda cr: events.append('guards') or []), \
                patch.object(loader, 'check_original_report_binding', side_effect=lambda env: events.append('binding')), \
                patch.object(loader.retention, 'retain_original_aliases', side_effect=retain):
            actual = cls._process_end(record, ['l10n_cl_simpledigital_payroll'])
        self.assertIs(actual, result)
        self.assertEqual(events, ['guards', 'binding', 'retain', 'original'])
        self.assertEqual(len(calls), 1)
        self.assertTrue(calls[0]['original_cleanup_delegated'])
        self.assertTrue(calls[0]['original_cleanup_cleared_loaded_set'])
        self.assertEqual(calls[0]['original_payslip_model_id'], 600)

    def test_guard_or_retention_failure_never_skips_into_cleanup_or_records_success(self):
        def original(self, modules):
            raise AssertionError('Must not delegate before guards pass')
        for stage in ('guard', 'retention'):
            cls, record, calls = self.wrapper(original)
            with patch.object(loader, 'check_database_guards', side_effect=ValueError('guard') if stage == 'guard' else None), \
                    patch.object(loader, 'check_original_report_binding'), \
                    patch.object(loader.retention, 'retain_original_aliases', side_effect=ValueError('retention')), \
                    self.assertRaises(ValueError):
                cls._process_end(record, ['l10n_cl_simpledigital_payroll'])
            self.assertFalse(calls)
            self.assertEqual(record.env.registry.loaded_xmlids, {'base.existing'})

    def test_original_cleanup_exception_propagates_without_success_receipt(self):
        def original(self, modules):
            raise ValueError('Real cleanup rejected by original guard')
        cls, record, calls = self.wrapper(original)
        with patch.object(loader, 'check_database_guards'), patch.object(loader, 'check_original_report_binding'), \
                patch.object(loader.retention, 'retain_original_aliases', return_value={}), \
                self.assertRaisesRegex(ValueError, 'Real cleanup rejected'):
            cls._process_end(record, ['l10n_cl_simpledigital_payroll'])
        self.assertFalse(calls)


if __name__ == '__main__':
    unittest.main()
