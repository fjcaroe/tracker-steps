"""Useful offline custody negatives, without Odoo, databases or customer data."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

import hr_consumer_metadata as metadata
import verify_original_bootstrap_evidence as verifier


class BootstrapEvidenceCase(unittest.TestCase):
    def test_artifact_code_is_inert_and_paths_cannot_escape(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            marker = root / 'must-not-exist'
            (root / 'payload.json').write_text(json.dumps({'code': "open(%r, 'w').write('executed')" % str(marker)}))
            self.assertIn('code', verifier.read(root, 'payload.json'))
            self.assertFalse(marker.exists())
            for path in ('../secret.json', '/secret.json', 'C:/secret.json'):
                with self.assertRaises(verifier.EvidenceError):
                    verifier.safe_path(root, path)

    def test_twelve_cold_tests_are_distinct_from_460_baseline_and_errors_rejected(self):
        verifier.test_result(['0 failed, 0 error(s) of 12 tests'], 12)
        for result in ('0 failed, 0 error(s) of 460 tests', '1 failed, 0 error(s) of 12 tests', '0 failed, 1 error(s) of 12 tests'):
            with self.assertRaises(verifier.EvidenceError):
                verifier.test_result([result], 12)
        with self.assertRaises(verifier.EvidenceError):
            verifier.no_flags({'historical_conversion': True}, ['historical_conversion'])

    def test_native_exact_business_and_only_three_declared_messages_are_admitted(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            native = root / 'cerro-reference'
            native.mkdir()
            source = {'tools/community/' + name: b'# synthetic trusted tool\n' for name in (
                'validate_payroll_api.py', 'validate_agriculture_core.py', 'offline_process.py')}
            source[str(metadata.SOURCE).replace('\\', '/')] = (Path(metadata.__file__).resolve().parents[2] / metadata.SOURCE).read_bytes()
            passed = {'test_results': ['0 failed, 0 error(s) of 294 tests'], 'expected_test_count': 294,
                'counts': {'installed': 391, 'enterprise': 140}, 'writes_to_source': False,
                'historical_conversion': False, 'simpledigital_certified': False, 'external_network_disabled': True,
                'loopback_http_only': True, 'postgres_unix_socket': True, 'accelerated_tools_sha256': {},
                'original_xmlid_noupdate_captured': True}
            for key, name in (('validator_sha256', 'validate_payroll_api.py'),
                    ('identity_snapshot_tool_sha256', 'validate_agriculture_core.py'), ('offline_runner_sha256', 'offline_process.py')):
                passed[key] = verifier.sha(source['tools/community/' + name])
            fields = []
            for ident, name in enumerate(metadata.EXPECTED, start=1):
                row = {'id': ident, 'model': metadata.MODEL, 'name': name, 'readonly': False}
                row.update(metadata.PREVIOUS[name])
                fields.append(row)
            original = {'ir_model_fields': fields, 'original_xmlids': [{'id': 1, 'module': 'synthetic', 'name': 'actual', 'noupdate': True}]}
            current = deepcopy(original)
            for row in current['ir_model_fields']:
                row.update(metadata.EXPECTED[row['name']])
            proof = metadata.verify(original, current)
            proof['source']['sha256'] = verifier.sha(source[proof['source']['path']])
            business = {'synthetic-%s' % index: {'rows': 0, 'hash': 'synthetic'} for index in range(1061)}
            values = {'business-before': business, 'business-after': business, 'history-before': {}, 'history-after': {},
                'identity-before': original, 'identity-after': current, 'hr-metadata-proof': proof}
            for name, value in values.items():
                (native / (name + '.json')).write_text(json.dumps(value))
            self.assertTrue(verifier.verify_native(root, source, passed)['history_exact'])
            current['ir_model_fields'][0]['readonly'] = True
            (native / 'identity-after.json').write_text(json.dumps(current))
            with self.assertRaisesRegex(AssertionError, 'metadata change'):
                verifier.verify_native(root, source, passed)
            (native / 'identity-after.json').write_text(json.dumps(values['identity-before']))
            damaged = deepcopy(business)
            damaged['synthetic-0']['hash'] = 'altered'
            (native / 'business-after.json').write_text(json.dumps(damaged))
            with self.assertRaisesRegex(verifier.EvidenceError, 'business/counters'):
                verifier.verify_native(root, source, passed)


if __name__ == '__main__':
    unittest.main()
