"""Run the exact XMLDSig crypto cases selected by Odoo, without a database."""
import ast
import importlib.util
from pathlib import Path
import sys
import types
import unittest


def main():
    source = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(source))
    import step_l10n_cl_edi_core  # noqa: F401
    package = 'step_l10n_cl_edi_core.tests'
    path = source / 'step_l10n_cl_edi_core/tests'
    # Do not run tests/__init__, which is rightly coupled to Odoo's test loader.
    module = types.ModuleType(package)
    module.__path__ = [str(path)]
    sys.modules[package] = module
    for name in ('ted_cases', 'certificate_trust_fixtures', 'dte_signature_cases'):
        spec = importlib.util.spec_from_file_location(package + '.' + name, path / (name + '.py'))
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
    node = next(row for row in ast.parse((path / 'test_dte_signature.py').read_text()).body
                if isinstance(row, ast.ClassDef) and row.name == 'TestDTESignatureCore')
    concrete = {row.name for row in node.body if isinstance(row, ast.FunctionDef) and row.name.startswith('test_')}
    shared = {name for name in module.DTESignatureCaseMixin.__dict__ if name.startswith('test_')}
    if concrete != shared | {'test_dte_signature_adds_no_parallel_model_or_counter'}:
        raise RuntimeError('Odoo DTE concrete test inventory differs from crypto cases')
    print('ODOO_DTE_SIGNATURE_TEST_METHODS %s' % len(concrete), flush=True)
    common = source / 'step_l10n_cl_caf_custody_core/tests/dte_signature_common.py'
    node = next(row for row in ast.parse(common.read_text()).body
        if isinstance(row, ast.ClassDef) and row.name == 'DTESignatureCustodyAssertions')
    assertions = {row.name.removeprefix('assert_') for row in node.body
        if isinstance(row, ast.FunctionDef) and row.name.startswith('assert_')}
    for addon, name in (('step_l10n_cl_caf_storage', 'TestDTESignatureCustodyStorage'),
                        ('step_l10n_cl_caf_native_reference', 'TestDTESignatureNativeCAFCustody')):
        node = next(row for row in ast.parse((source / addon / 'tests/test_dte_signature.py').read_text()).body
            if isinstance(row, ast.ClassDef) and row.name == name)
        methods = [row for row in node.body if isinstance(row, ast.FunctionDef) and row.name.startswith('test_')]
        delegates = set()
        for method in methods:
            calls = [item.func.attr.removeprefix('assert_') for item in ast.walk(method)
                     if isinstance(item, ast.Call) and isinstance(item.func, ast.Attribute)
                     and isinstance(item.func.value, ast.Name) and item.func.value.id == 'self'
                     and item.func.attr.startswith('assert_')]
            if len(calls) != 1:
                raise RuntimeError('Each concrete custody test must invoke one shared actor case')
            delegates.add(calls[0])
        if delegates != assertions or len(methods) != len(assertions) or len(methods) != 6:
            raise RuntimeError('Custody DTE concrete selection differs from shared actor cases')
        print('%s_TEST_METHODS %s' % (name, len(methods)), flush=True)
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(type('TestDTESignatureCore',
        (module.DTESignatureCaseMixin, unittest.TestCase), {}))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    raise SystemExit(main())
