"""Offline boundary checks; no payroll model or PDF output is fabricated."""
import hashlib
from pathlib import Path
import tempfile
import unittest

from verify_original_report_headers import HeaderReviewError, checked_file, checked_pipeline, header_contract, pixel_difference, private_file


class HeaderEvidenceCase(unittest.TestCase):
    def test_pipeline_requires_both_functional_hash_and_bytes_even_in_diagnostic_mode(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            raw = b'{"prepare_calls": []}'
            (root / 'pipeline.json').write_bytes(raw)
            entry = {'pipeline': 'pipeline.json', 'pipeline_sha256': hashlib.sha256(raw).hexdigest(),
                     'pipeline_bytes': len(raw)}
            self.assertTrue(checked_pipeline(root, entry)[2])
            for changed in ({'pipeline_sha256': '0' * 64}, {'pipeline_bytes': len(raw) - 1}):
                with self.assertRaises(HeaderReviewError):
                    checked_pipeline(root, dict(entry, **changed), True)
            with self.assertRaises(HeaderReviewError):
                checked_pipeline(root, {'pipeline': 'pipeline.json'})
            self.assertFalse(checked_pipeline(root, {'pipeline': 'pipeline.json'}, True)[2])

    def test_alpha_split_accepts_only_one_channel_level_of_encoding_difference(self):
        result = pixel_difference(bytes([20, 40, 80, 255, 255, 255]), bytes([21, 39, 80, 255, 255, 255]))
        self.assertTrue(result['matches'])
        self.assertEqual(result['maximum_channel_error'], 1)
        self.assertFalse(pixel_difference(bytes([20, 40, 80]), bytes([22, 40, 80]))['matches'])
        self.assertIsNone(pixel_difference(b'123', b'12'))

    def test_header_presence_checks_text_rather_than_untrusted_markers(self):
        raw = b'<html><body><div class="header"><p>Private company</p><p>Chile</p></div></body></html>'
        contract = header_contract(raw, 'Private company', 'Chile')
        self.assertTrue(contract['company_name_present'])
        self.assertTrue(contract['country_name_present'])
        self.assertEqual(contract['logos'], [])
        contract = header_contract(b'<p data-company="Private company" data-country="Chile">Other</p>',
                                   'Private company', 'Chile')
        self.assertFalse(contract['company_name_present'])
        self.assertFalse(contract['country_name_present'])

    def test_logo_must_be_original_embedded_data_not_a_remote_placeholder(self):
        with self.assertRaisesRegex(HeaderReviewError, 'original embedded'):
            header_contract(b'<p>Company Chile</p><img alt="Logo" src="https://invalid.example/logo.png"/>',
                            'Company', 'Chile')

    def test_paths_cannot_escape_or_select_an_absolute_evidence_file(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            for value in ('../escaped', str(root / 'absolute'), None, True):
                with self.assertRaises(HeaderReviewError):
                    private_file(root, value)

    def test_hash_and_length_must_both_match_before_inspection(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            raw = b'<html>Captured original header bytes</html>'
            (root / 'header.html').write_bytes(raw)
            entry = {'file': 'header.html', 'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)}
            self.assertEqual(checked_file(root, entry)[1], raw)
            for changed in ({'sha256': '0' * 64}, {'bytes': len(raw) - 1}):
                with self.assertRaises(HeaderReviewError):
                    checked_file(root, dict(entry, **changed))


if __name__ == '__main__':
    unittest.main()
