"""Synthetic complete-inventory replay; no Odoo, database or artifact code."""
from contextlib import ExitStack
from copy import deepcopy
import json
from pathlib import Path
import unittest
from unittest.mock import patch

import original_history_engine_contract as contract
import test_derive_original_payroll_storage as storage_fixture
from test_derive_original_history_deletion import BODY
import test_build_numeric_input_engine as numeric_fixture


def fixture():
    files = storage_fixture.provider()
    files[contract.numeric.FILE] = numeric_fixture.NumericEngineCase().source()[contract.numeric.FILE]
    files[contract.deletion.FILE] = BODY
    for index in range(144 - len(files)):
        files['synthetic-fixture/unmodified-%03d.txt' % index] = b'explicit unit fixture, not operational vendor data\n'
    raw = json.dumps(storage_fixture.schema_plan(), sort_keys=True).encode()
    root = Path(__file__).resolve().parents[2]
    guards = {name: (root / name).read_bytes() for name in contract.GUARD_PATHS}
    return files, raw, guards


def pinned_fixture(files, raw):
    stack = ExitStack()
    stack.enter_context(patch.object(contract.storage, 'PINNED_SOURCE', {
        name: contract.sha(files[name]) for name in contract.storage.PINNED_SOURCE}))
    stack.enter_context(patch.object(contract.deletion, 'SOURCE_SHA256', contract.sha(files[contract.deletion.FILE])))
    stack.enter_context(patch.object(contract.storage, 'SCHEMA_PLAN_SHA256', contract.sha(raw)))
    return stack


class CompositionCase(unittest.TestCase):
    def test_four_full_inventories_replay_without_mutating_original_or_claiming_final_numeric(self):
        original, raw, guard = fixture(); before = dict(original)
        with pinned_fixture(original, raw):
            candidate, report = contract.compose(original, raw, guard)
            proof = contract.verify_snapshots(original, candidate, report, raw, guard)
        self.assertEqual(original, before)
        self.assertEqual(len(report['original_source_files']), 144)
        self.assertEqual(len(report['candidate_files']), 144)
        self.assertEqual([len(stage['after_files']) for stage in report['stages']], [144, 144, 144])
        self.assertEqual(report['stages'][0]['before_files'], report['original_source_files'])
        self.assertEqual(report['stages'][0]['after_files'], report['stages'][1]['before_files'])
        self.assertEqual(report['stages'][1]['after_files'], report['stages'][2]['before_files'])
        self.assertEqual(report['stages'][2]['after_files'], report['candidate_files'])
        self.assertNotEqual(report['stages'][0]['after_files'], report['candidate_files'])
        self.assertTrue(report['numeric_receipt_describes_intermediate_only'])
        self.assertTrue(proof['methods_defaults_imports_and_model_identities_exact'])
        self.assertFalse(proof['operational_acceptance'])
        self.assertFalse(proof['vendor_git_proof_verified_by_this_function'])

    def test_partial_or_tampered_final_bytes_and_report_never_replay(self):
        original, raw, guard = fixture()
        with pinned_fixture(original, raw):
            candidate, report = contract.compose(original, raw, guard)
            for kind in ('numeric-only', 'changed-file', 'extra-file', 'missing-file'):
                changed = dict(candidate)
                if kind == 'numeric-only': changed = contract.numeric.plan(original)
                elif kind == 'changed-file': changed[contract.deletion.FILE] += b'\n# unreviewed\n'
                elif kind == 'extra-file': changed['extra.py'] = b'# unreviewed\n'
                else: changed.pop('__manifest__.py')
                with self.subTest(kind=kind), self.assertRaises(ValueError):
                    contract.verify_snapshots(original, changed, report, raw, guard)
            for name in ('candidate_files', 'stages', 'actual_api_guard', 'operational_acceptance'):
                changed = deepcopy(report)
                if name == 'operational_acceptance': changed[name] = True
                elif name == 'stages': changed[name][0]['complete_file_count'] = 143
                elif name == 'actual_api_guard': changed[name]['context_or_marker_authority'] = True
                else: changed[name]['__manifest__.py'] = '0' * 64
                with self.subTest(name=name), self.assertRaises(ValueError):
                    contract.verify_snapshots(original, candidate, changed, raw, guard)

    def test_guard_package_required_before_any_cascade_derivation(self):
        original, raw, guard = fixture()
        for kind in ('missing', 'not-imported', 'old-version', 'changed-guard', 'no-op-provider-check-removed', 'only-marker'):
            changed = dict(guard)
            if kind == 'missing': changed.pop(contract.GUARD_FILE)
            elif kind == 'not-imported': changed['step_payroll_oca_api/models/__init__.py'] = b'# no guard\n'
            elif kind == 'old-version': changed['step_payroll_oca_api/__manifest__.py'] = b"{'version':'18.0.1.16.0','license':'LGPL-3'}"
            elif kind == 'changed-guard': changed[contract.GUARD_FILE] = changed[contract.GUARD_FILE].replace(b'sudo(False)', b'sudo(True)')
            elif kind == 'no-op-provider-check-removed':
                changed[contract.GUARD_FILE] = changed[contract.GUARD_FILE].replace(
                    b'if remaining:', b'if False:', 1)
                self.assertNotEqual(contract.sha(changed[contract.GUARD_FILE]), contract.sha(guard[contract.GUARD_FILE]))
            else: changed[contract.GUARD_FILE] = b'guard_present=True\n'
            with pinned_fixture(original, raw), patch.object(contract.deletion, 'plan_history_deletion') as invoked:
                with self.subTest(kind=kind), self.assertRaises(ValueError): contract.compose(original, raw, changed)
                invoked.assert_not_called()
        proof = contract.guard_contract(guard)
        self.assertTrue(proof['actual_import_chain_validated'])
        self.assertFalse(proof['runtime_guard_execution_certified'])

    def test_plan_seal_paths_and_anchored_or_duplicate_transform_are_rejected(self):
        original, raw, guard = fixture()
        with self.assertRaisesRegex(ValueError, 'plan6977'): contract.compose(original, raw, guard)
        with pinned_fixture(original, raw):
            candidate, unused = contract.compose(original, raw, guard)
            with self.assertRaises(ValueError): contract.compose(candidate, raw, guard)
        for name in ('../escape.py', '/absolute.py', 'sub/../escape.py', 'cache/__pycache__/x.py', 'cached.pyc'):
            changed = dict(original); body = changed.pop(next(key for key in changed if key.startswith('synthetic-fixture/')))
            changed[name] = body
            with self.subTest(name=name), self.assertRaises(ValueError): contract.inventory(changed)

    def test_readonly_composition_code_has_no_database_or_artifact_execution_surface(self):
        import ast
        tree = ast.parse(Path(contract.__file__).read_text())
        calls = {node.func.attr for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)}
        self.assertFalse(calls & {'execute', 'connect', 'db_connect', 'sudo', 'compute_sheet', 'commit', 'exec_module', 'load_module'})
        names = {node.func.id for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)}
        self.assertFalse(names & {'exec', 'eval', '__import__'})


if __name__ == '__main__':
    unittest.main()
