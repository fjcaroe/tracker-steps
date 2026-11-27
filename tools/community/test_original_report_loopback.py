import re
import unittest
from unittest.mock import Mock, patch

from original_report_loopback import pdf_derivative_name, run


class OriginalReportLoopbackCase(unittest.TestCase):
    def test_service_account_owns_the_server_and_closes_it_when_the_shell_fails(self):
        command = ['env', 'PYTHONDONTWRITEBYTECODE=1', 'python3', 'odoo-bin', 'shell', '-d', 'PRIVATE',
                   '--stop-after-init', '--no-http']
        server = Mock()
        server.poll.return_value = None
        with patch('original_report_loopback.os.geteuid', return_value=42, create=True), \
             patch('original_report_loopback.build_opener') as opener, \
             patch('original_report_loopback.subprocess.Popen', return_value=server) as start, \
             patch('original_report_loopback.subprocess.run', side_effect=RuntimeError('shell')) as shell:
            opener.return_value.open.return_value.__enter__.return_value.status = 200
            with self.assertRaisesRegex(RuntimeError, 'shell'):
                run(command, service_process=True)
            url = shell.call_args.kwargs['env']['STEPS_PRIVATE_REPORT_URL']
            self.assertTrue(url.startswith('http://127.0.0.1:'))
            self.assertEqual(shell.call_args.args[0], command)
            self.assertIn('--http-port='+url.rsplit(':',1)[1], start.call_args.args[0])
            self.assertNotIn('shell', start.call_args.args[0])
            server.terminate.assert_called_once()
            server.wait.assert_called_once_with(timeout=15)

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
