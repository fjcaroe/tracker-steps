import re
import unittest

from original_report_loopback import pdf_derivative_name


class OriginalReportLoopbackCase(unittest.TestCase):
    def test_derivative_keeps_both_original_private_prefixes_within_postgres_limit(self):
        for mode in ('HANDOVER', 'REFERENCE'):
            prefix = f'MANAGEMENT_QA_CERRO_PAYROLL_API_ORIGINAL_{mode}_'
            source = prefix + 'a' * (63 - len(prefix))
            name = pdf_derivative_name(source)
            self.assertLessEqual(len(name), 63)
            self.assertRegex(name, re.escape(prefix) + r'PDF_[0-9a-f]{8}$')
            self.assertNotEqual(name, pdf_derivative_name(source[:-1] + 'b'))
        with self.assertRaises(ValueError):
            pdf_derivative_name('CERRO_EL_PLOMO')
