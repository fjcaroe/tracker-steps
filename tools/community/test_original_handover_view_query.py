"""Observed code contract only; no database, Odoo or source visibility oracle."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import original_handover_view_query as view
import probe_original_handover as probe


class CoreViewQueryCase(unittest.TestCase):
    def test_only_observed_sql_bytes_match_not_generic_or_mutating_ctes(self):
        self.assertEqual(view.sha(view.QUERY.encode()), view.QUERY_SHA256)
        self.assertTrue(view.is_exact_query(view.QUERY))
        changes = [
            view.QUERY.replace('FALSE OR', 'TRUE OR'),
            view.QUERY.replace('"active" = TRUE', '"active" = FALSE'),
            view.QUERY.replace('"website_id" IS NULL', '"website_id" IS NOT NULL'),
            view.QUERY.replace('FROM ir_ui_view', 'FROM hr_payslip'),
            view.QUERY.replace('SELECT id, inherit_id, priority, mode, model', 'DELETE FROM ir_ui_view RETURNING id'),
            view.QUERY.replace('WITH RECURSIVE', 'WITH mutation AS (UPDATE ir_ui_view SET active=false RETURNING id), RECURSIVE'),
            view.QUERY.replace('v.id, v.inherit_id, v.mode', "v.id, pg_read_file('/etc/passwd'), v.mode"),
            view.QUERY.replace('v.id, v.inherit_id, v.mode', "v.id, dblink('external','UPDATE data'), v.mode"),
            view.QUERY.replace('v.id, v.inherit_id, v.mode', "v.id, nextval('ir_sequence_1'), v.mode"),
            view.QUERY + '; DELETE FROM ir_ui_view',
            'WITH x AS (SELECT id FROM ir_ui_view) SELECT * FROM x',
        ]
        for code in changes:
            with self.subTest(sha=view.sha(code.encode())):
                self.assertFalse(view.is_exact_query(code))
        # The generic lexer remains strict: a bare WITH is never admitted.
        with self.assertRaises(probe.ProbeBlocked): probe.admit_sql(view.QUERY)

    def test_actual_observer_requires_origin_before_delegating_original_query(self):
        class Cursor:
            def __init__(self): self.calls = []
            def execute(self, query, *args, **kwargs):
                self.calls.append((query, args, kwargs))
                return 'real-result-unchanged'
        cursor = Cursor()
        with self.assertRaises(view.ViewQueryBlocked):
            with probe.observe_cursor(cursor): cursor.execute(view.QUERY)
        self.assertEqual(cursor.calls, [])
        proof = {'observed-code-and-pinned-origin': 'synthetic-boundary-fixture'}
        parameter = ('synthetic-view-id-bound-parameter',)
        with patch.object(view, 'current_origin', return_value=proof):
            with probe.observe_cursor(cursor) as observation:
                self.assertEqual(cursor.execute(view.QUERY, parameter), 'real-result-unchanged')
                self.assertEqual(observation['pinned_core_view_queries'], {'count': 1, 'contract': proof})
        self.assertEqual(cursor.calls, [(view.QUERY, (parameter,), {})])

    def test_both_real_builder_frames_and_same_runtime_are_mandatory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            frames = []
            for module, spec in view.SPECS.items():
                path = root / spec['relative']; path.parent.mkdir(parents=True, exist_ok=True); path.write_text('fixture')
                frames.append({'module': module, 'function': '_get_inheriting_views', 'file': str(path)})
            def inspector(path, module, key):
                spec = view.SPECS[module]
                return {'runtime_root': str(root), 'module': module, 'file': path,
                    'file_sha256': spec['sha256'], 'runtime_git_pin': view.PIN,
                    'method_source_sha256': dict(spec['methods'])}
            proof = view.bind_origin(frames, inspector)
            self.assertTrue(proof['metadata_select_only'])
            self.assertFalse(proof['generic_with_admitted'])
            for altered in (frames[:1], frames[1:], frames + [frames[0]],
                    [dict(frames[0], function='arbitrary_caller'), frames[1]]):
                with self.assertRaises(view.ViewQueryBlocked): view.bind_origin(altered, inspector)
            with self.assertRaises(view.ViewQueryBlocked):
                view.bind_origin(frames, lambda path, module, key: {'runtime_root': module})
            # A caller cannot forge an official module name while its on-disk
            # file differs from the exact approved LGPL source.
            with self.assertRaises(view.ViewQueryBlocked): view.bind_origin(frames)

    def test_git_origin_uses_explicit_readonly_repository_under_old_git(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            (root / '.git').mkdir()
            view.git_origin.cache_clear()
            with patch.object(view.subprocess, 'check_output', return_value=(view.PIN + '\n').encode()) as run:
                self.assertEqual(view.git_origin(str(root)), view.PIN)
            args = run.call_args.args[0]
            self.assertIn('--no-optional-locks', args)
            self.assertIn('--git-dir=' + str(root / '.git'), args)
            self.assertIn('--work-tree=' + str(root), args)
            self.assertIn('safe.directory=' + str(root), args)
            self.assertNotIn('-C', args)
            self.assertNotIn('--global', args)
            self.assertEqual(args[-2:], ['rev-parse', 'HEAD'])
            view.git_origin.cache_clear()
            with patch.object(view.subprocess, 'check_output', return_value=b'wrong-pin\n'):
                with self.assertRaises(view.ViewQueryBlocked): view.git_origin(str(root))
        view.git_origin.cache_clear()


if __name__ == '__main__':
    unittest.main()
