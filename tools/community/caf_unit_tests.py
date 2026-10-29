"""Run CAF crypto/XML cases without an Odoo server or database."""
import ast
import importlib.util
from pathlib import Path
import sys
import unittest


def main():
    source = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(source))
    path = source / 'step_l10n_cl_edi_core/tests/caf_cases.py'
    import step_l10n_cl_edi_core  # establish the package without importing Odoo tests
    spec = importlib.util.spec_from_file_location('step_l10n_cl_edi_core.tests.caf_cases', path)
    cases = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cases)
    # Check the same concrete-class method inventory used by Odoo's loader.
    # Merely inheriting the mixin leaves these cases invisible to that loader.
    odoo_path = source / 'step_l10n_cl_edi_core/tests/test_caf.py'
    odoo_class = next(node for node in ast.parse(odoo_path.read_text()).body
                      if isinstance(node, ast.ClassDef) and node.name == 'TestCAFCore')
    concrete = {node.name for node in odoo_class.body
                if isinstance(node, ast.FunctionDef) and node.name.startswith('test_')}
    shared = {name for name in cases.CAFCaseMixin.__dict__ if name.startswith('test_')}
    if concrete != shared | {'test_core_has_no_parallel_model_or_counter'}:
        raise RuntimeError('Odoo CAF test inventory differs from shared crypto cases')
    print('ODOO_CAF_TEST_METHODS %s' % len(concrete), flush=True)
    test_class = type('TestCAFCore', (cases.CAFCaseMixin, unittest.TestCase), {})
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(test_class)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    raise SystemExit(main())
