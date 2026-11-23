"""Private HTTP tests retain external egress denial and remove their exact rule."""
from types import SimpleNamespace
import unittest
from unittest.mock import patch
try:
    import pwd
except ModuleNotFoundError:  # Windows authoring; the operation runs on Linux.
    with patch.dict('sys.modules', {'pwd': SimpleNamespace(getpwnam=lambda name: None)}):
        from private_report_http import customer_qa_test_loopback
else:
    from private_report_http import customer_qa_test_loopback


class LoopbackCase(unittest.TestCase):
    def test_exact_endpoint_removed_after_success_and_failure(self):
        for failure in (False, True):
            with self.subTest(failure=failure), patch('private_report_http.os.geteuid', return_value=0), \
                    patch('private_report_http.pwd.getpwnam', return_value=SimpleNamespace(pw_uid=992)), \
                    patch('private_report_http.subprocess.run', side_effect=[
                        SimpleNamespace(returncode=1), SimpleNamespace(returncode=0),
                        SimpleNamespace(returncode=0), SimpleNamespace(returncode=1)]) as run:
                try:
                    with customer_qa_test_loopback('MANAGEMENT_QA_QA-CERRO_t231232_43b2c8e1', 12345, {'db_user': 'cerroqa_odoo18'}):
                        if failure:
                            raise RuntimeError('private test failed')
                except RuntimeError:
                    self.assertTrue(failure)
                inserted = run.call_args_list[1].args[0]
                removed = run.call_args_list[2].args[0]
                self.assertEqual(inserted[5:], removed[4:])
                self.assertIn('127.0.0.1/32', inserted)
                self.assertEqual(inserted[inserted.index('--dport')+1], '12345')
                self.assertEqual(inserted[inserted.index('--uid-owner')+1], '992')

    def test_original_database_is_rejected_before_firewall_access(self):
        with patch('private_report_http.os.geteuid', return_value=0), \
                patch('private_report_http.subprocess.run') as run:
            with self.assertRaises(AssertionError):
                with customer_qa_test_loopback('QA-CERROELPLOMO', 12345, {'db_user': 'cerroqa_odoo18'}):
                    pass
            run.assert_not_called()


if __name__ == '__main__':
    unittest.main()
