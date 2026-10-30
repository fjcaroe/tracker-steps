"""Run the same TED crypto cases selected by Odoo, without a database."""
import ast
import importlib.util
from pathlib import Path
import sys
import unittest


def main():
    source = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(source))
    import step_l10n_cl_edi_core
    path = source / 'step_l10n_cl_edi_core/tests/ted_cases.py'
    spec = importlib.util.spec_from_file_location('step_l10n_cl_edi_core.tests.ted_cases', path)
    cases = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cases)
    node = next(row for row in ast.parse((path.parent / 'test_ted.py').read_text()).body
                if isinstance(row, ast.ClassDef) and row.name == 'TestTEDCore')
    concrete = {row.name for row in node.body if isinstance(row, ast.FunctionDef) and row.name.startswith('test_')}
    shared = {name for name in cases.TEDCaseMixin.__dict__ if name.startswith('test_')}
    if concrete != shared | {'test_ted_adds_no_parallel_model_or_counter'}:
        raise RuntimeError('Odoo TED concrete test inventory differs from crypto cases')
    print('ODOO_TED_TEST_METHODS %s' % len(concrete), flush=True)
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(type('TestTEDCore', (cases.TEDCaseMixin, unittest.TestCase), {}))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    raise SystemExit(main())
