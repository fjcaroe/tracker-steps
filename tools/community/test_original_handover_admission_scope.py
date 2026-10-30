"""Explicit data-only scope; no Odoo engine, database, grants or acceptance."""
import ast
import contextlib
import io
from pathlib import Path
import unittest
from types import SimpleNamespace
import tempfile

import probe_original_handover as probe
import resume_original_anchor_probe as resumer


class AdmissionScopeCase(unittest.TestCase):
    def test_projection_requires_a_real_sealed_source_before_any_environment_access(self):
        class Env:
            @property
            def cr(self): raise AssertionError('database touched before scope admission')
        for path, digest in ((None, None), ('/private/source.json', None),
                             (None, 'a' * 64), ('/private/source.json', 'unsealed')):
            with self.subTest(path=path, digest=digest), self.assertRaisesRegex(probe.ProbeBlocked, 'sealed-actual-native'):
                probe.run(Env(), None, None, None, None, None, admission_scope='projection-only',
                    source_visibility_path=path, source_visibility_sha256=digest)
        for scope in ('skip-ui', 'project-all', '', None, True):
            with self.subTest(scope=scope), self.assertRaisesRegex(probe.ProbeBlocked, 'unknown-original'):
                probe.run(Env(), None, None, None, None, None, admission_scope=scope)

    def test_default_is_full_and_receipts_cannot_be_confused(self):
        self.assertEqual(probe.admission_scope_contract('full'), 'full')
        self.assertEqual(probe.admission_scope_contract('projection-only', '/private/actual-source.json', 'a' * 64),
            'projection-only')
        self.assertEqual(probe.admission_receipt_name('full'), 'cohort-admission.json')
        self.assertEqual(probe.admission_receipt_name('projection-only'), 'cohort-projection-admission.json')
        for scope in ('FULL', 'skip-ui', None):
            with self.assertRaises(probe.ProbeBlocked): probe.admission_receipt_name(scope)
        argv = ['--root', '/private/root', '--tools', '/private/tools', '--source-visibility', '/private/source',
            '--attempt', 'new']
        self.assertEqual(resumer.parse_arguments(argv).admission_scope, 'full')
        self.assertEqual(resumer.parse_arguments(argv + ['--admission-scope', 'projection-only']).admission_scope,
            'projection-only')
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            resumer.parse_arguments(argv + ['--admission-scope', 'skip-ui'])

    def test_postcheck_rejects_unsealed_projection_before_creating_technical_acls(self):
        tree = ast.parse(Path(__file__).with_name('postcheck_original_anchor.py').read_text(encoding='utf-8'))
        method = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'run')
        namespace = {'admission_scope_contract': probe.admission_scope_contract}
        exec(compile(ast.Module(body=[method], type_ignores=[]), '<actual-postcheck-scope-boundary>', 'exec'), namespace)
        with self.assertRaisesRegex(probe.ProbeBlocked, 'sealed-actual-native'):
            namespace['run'](object(), '/private/not-opened', database='not-opened', reference='not-opened',
                capsule_sha256='not-opened', identity_sha256='not-opened', admission_scope='projection-only')
        database = 'MANAGEMENT_QA_CERRO_PAYROLL_API_ORIGINAL_HANDOVER_UNIT'
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder, 'invalid-source.json')
            calls = []
            def sealed(path, digest):
                calls.append(Path(path).name)
                if Path(path) == source: raise probe.ProbeBlocked('source-seal-rejected')
                return {}
            namespace.update(Path=Path, re=__import__('re'), sealed_json=sealed,
                admission_receipt_name=probe.admission_receipt_name,
                menu_witness_arguments=probe.menu_witness_arguments)
            with self.assertRaisesRegex(probe.ProbeBlocked, 'source-seal-rejected'):
                namespace['run'](SimpleNamespace(cr=SimpleNamespace(dbname=database)), folder,
                    database=database, reference=database.replace('_HANDOVER_', '_REFERENCE_'),
                    capsule_sha256='a' * 64, identity_sha256='b' * 64, admission_scope='projection-only',
                    source_visibility_path=source, source_visibility_sha256='c' * 64)
            self.assertEqual(calls, ['capsule.json', 'identity-before.json', 'invalid-source.json'])

    def test_ui_calls_are_exclusive_to_full_branch_and_real_projection_has_no_scope_bypass(self):
        tree = ast.parse(Path(probe.__file__).read_text(encoding='utf-8'))
        run = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'run')
        ui_names = {'forms_and_menus', 'legacy_menu_boundaries', 'report_route'}
        all_ui = [node for node in ast.walk(run) if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name) and node.func.id in ui_names]
        branches = [node for node in ast.walk(run) if isinstance(node, ast.If)
            and ast.unparse(node.test) == "admission_scope == 'full'"]
        self.assertEqual(len(branches), 1)
        guarded_ui = [node for statement in branches[0].body for node in ast.walk(statement)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in ui_names]
        self.assertEqual(len(all_ui), 3)
        self.assertEqual(set(map(id, all_ui)), set(map(id, guarded_ui)))
        # Scope never changes the actual projection method, root UID, rule
        # pairs or SQL INSERT shape. Both modes reach the same normal API.
        actual = [node for node in ast.walk(run) if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == '_step_materialize_original_rule_projection']
        self.assertEqual(len(actual), 1)
        self.assertEqual(ast.unparse(actual[0].func.value), 'structures')

    def test_reusing_prepared_technical_acl_never_grants_or_rewrites_collisions(self):
        tree = ast.parse(Path(__file__).with_name('postcheck_original_anchor.py').read_text(encoding='utf-8'))
        method = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
            and node.name == 'verify_reusable_read_acl')
        namespace = {}
        exec(compile(ast.Module(body=[method], type_ignores=[]), '<actual-empty-model-acl-boundary>', 'exec'), namespace)
        class ACL:
            def __init__(self, count=1, group=46, read=True, write=False, create=False, unlink=False):
                self.count = count; self.group_id = SimpleNamespace(id=group)
                self.perm_read, self.perm_write, self.perm_create, self.perm_unlink = read, write, create, unlink
            def __len__(self): return self.count
        namespace['verify_reusable_read_acl'](ACL(), 46)
        for change in ({'count': 2}, {'group': 1}, {'read': False}, {'write': True},
                       {'create': True}, {'unlink': True}):
            with self.subTest(change=change), self.assertRaises(AssertionError):
                namespace['verify_reusable_read_acl'](ACL(**change), 46)


if __name__ == '__main__':
    unittest.main()
