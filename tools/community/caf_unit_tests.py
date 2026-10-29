"""Run CAF crypto/XML cases without an Odoo server or database."""
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
    test_class = type('TestCAFCore', (cases.CAFCaseMixin, unittest.TestCase), {})
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(test_class)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    raise SystemExit(main())
