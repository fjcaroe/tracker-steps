"""A package cannot widen Demo-SYS beyond the live SyS reference."""
import unittest

from demo_sys_scope import check_modules


class DemoSysScopeTests(unittest.TestCase):
    def test_existing_accounting_and_payroll_are_in_scope(self):
        self.assertEqual(check_modules(['account', 'payroll'], ['account', 'payroll', 'base']), {'account', 'payroll'})

    def test_extra_packing_is_refused_even_in_mixed_package(self):
        with self.assertRaisesRegex(ValueError, 'step_packing'):
            check_modules(['payroll', 'step_packing'], ['payroll', 'base'])

    def test_new_dependency_cannot_smuggle_an_agricultural_app(self):
        with self.assertRaisesRegex(ValueError, 'step_hr'):
            check_modules(['payroll'], ['payroll', 'base'], {'payroll': ['base', 'step_hr']})

    def test_dependency_cycles_terminate(self):
        self.assertEqual(check_modules(['payroll'], ['payroll', 'base'],
                         {'payroll': ['base'], 'base': ['payroll']}), {'payroll', 'base'})


if __name__ == '__main__':
    unittest.main()
