"""Run the same EnvioDTE crypto cases selected by Odoo, entirely offline."""
import ast
import importlib.util
from pathlib import Path
import sys
import types
import unittest


def main():
    root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(root))
    import step_l10n_cl_edi_core  # noqa: F401
    package = 'step_l10n_cl_edi_core.tests'
    path = root / 'step_l10n_cl_edi_core/tests'
    module = types.ModuleType(package)
    module.__path__ = [str(path)]
    sys.modules[package] = module
    for name in ('ted_cases', 'dte_signature_cases', 'envelope_cases'):
        spec = importlib.util.spec_from_file_location(package + '.' + name, path / (name + '.py'))
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
    node = next(row for row in ast.parse((path / 'test_envelope.py').read_text()).body
        if isinstance(row, ast.ClassDef) and row.name == 'TestEnvioDTECore')
    concrete = {row.name for row in node.body if isinstance(row, ast.FunctionDef) and row.name.startswith('test_')}
    shared = {name for name in module.EnvelopeCaseMixin.__dict__ if name.startswith('test_')}
    if concrete != shared | {'test_envelope_adds_no_parallel_model_counter_or_acl'}:
        raise RuntimeError('Odoo EnvioDTE concrete selection differs from shared crypto cases')
    print('ODOO_ENVIODTE_TEST_METHODS %s' % len(concrete), flush=True)
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(type('TestEnvioDTECore',
        (module.EnvelopeCaseMixin, unittest.TestCase), {}))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    raise SystemExit(main())
