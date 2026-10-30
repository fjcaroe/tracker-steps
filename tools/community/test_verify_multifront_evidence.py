"""Offline policy negatives; all evidence in these tests is synthetic."""
import ast
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import verify_multifront_evidence as verifier


def write(root, name, value):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding='utf-8')


def packet_fixture():
    provider = {'__manifest__.py': repr({'license': 'AGPL-3'}).encode()}
    provider.update({'synthetic_%02d.txt' % index: str(index).encode() for index in range(51)})
    source = {module + '/__manifest__.py': repr({'license': 'LGPL-3', 'version': '18.0.1.0.0'}).encode()
              for module in verifier.OWN_MODULES}
    source['tools/community/simpledigital_runtime_source.json'] = json.dumps(
        {'files': {name: verifier.sha(body) for name, body in provider.items()}}).encode()
    packet = {name: verifier.sha(body) for name, body in source.items() if name.split('/')[0] in verifier.OWN_MODULES}
    packet.update({verifier.builder.MODULE + '/' + name: verifier.sha(body) for name, body in provider.items()})
    return source, provider, packet


class MultifrontEvidenceCase(unittest.TestCase):
    def test_exact_27_and_normal_52_packet_rejects_cold_missing_extra_and_hash_drift(self):
        source, provider, packet = packet_fixture()
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for provider_folder in ('original-provider', 'normal-provider'):
                path = root / provider_folder / '__manifest__.py'
                path.parent.mkdir(parents=True)
                path.write_bytes(provider['__manifest__.py'])
            for mode in verifier.EXPECTED_TESTS:
                write(root, mode + '/source-files.json', packet)
            with patch.object(verifier.previous.base, 'addon_snapshot', return_value=provider), \
                    patch.object(verifier.previous, 'replay_normal_provider', return_value=provider):
                self.assertEqual(verifier.verify_packets(root, source), packet)
                for edit in ('missing', 'extra', 'hash', 'native'):
                    changed = deepcopy(packet)
                    if edit == 'missing': changed.pop(next(iter(changed)))
                    elif edit == 'extra': changed['unreviewed_addon/__manifest__.py'] = 'f' * 64
                    else: changed[next(iter(changed))] = 'f' * 64
                    for mode in verifier.EXPECTED_TESTS:
                        write(root, mode + '/source-files.json', changed if edit != 'native' or mode == 'cerro-reference' else packet)
                    with self.subTest(edit=edit), self.assertRaises(verifier.base.EvidenceError):
                        verifier.verify_packets(root, source)
                for mode in verifier.EXPECTED_TESTS:
                    write(root, mode + '/source-files.json', packet)
            cold = dict(list(provider.items())[:49])
            with patch.object(verifier.previous.base, 'addon_snapshot', return_value=cold):
                with self.assertRaisesRegex(verifier.base.EvidenceError, '52-file'):
                    verifier.verify_packets(root, source)

    def test_103_97_new_functional_methods_must_run_exactly_once(self):
        root = Path(__file__).resolve().parents[2]
        source = {path.relative_to(root).as_posix(): path.read_bytes() for module in verifier.OWN_MODULES
                  for path in (root / module).rglob('*.py')}
        for mode, expected in (('community', 103), ('cerro-reference', 97)):
            modules = verifier.NEW_MODULES if mode == 'community' else verifier.NEW_MODULES[:-1]
            keys = []
            for name, body in source.items():
                if '/tests/test_' not in name:
                    continue
                for cls in ast.parse(body.decode('utf-8-sig')).body:
                    if not isinstance(cls, ast.ClassDef):
                        continue
                    admitted = name.split('/')[0] in modules or cls.name == 'TestTEDCore' or cls.name == (
                        'TestTEDCustodyStorage' if mode == 'community' else 'TestTEDNativeCAFCustody')
                    if admitted:
                        keys += [cls.name + '.' + method.name for method in cls.body
                            if isinstance(method, ast.FunctionDef) and method.name.startswith('test_')]
            self.assertEqual(len(keys), expected)
            log = '\n'.join('Starting ' + key + ' ...' for key in keys)
            self.assertEqual(verifier.critical_methods(source, log, mode), expected)
            for changed in (log.replace('Starting ' + keys[0] + ' ...', ''), log + '\nStarting ' + keys[0] + ' ...'):
                with self.assertRaises(verifier.base.EvidenceError):
                    verifier.critical_methods(source, changed, mode)

    def test_capsule_manifest_detects_changed_missing_and_surplus_members(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            body = b'private synthetic metadata only'
            (root / 'metadata.json').write_bytes(body)
            receipt = {'schema': 1, 'files': {'metadata.json': verifier.sha(body)}, 'database_accessed': False,
                'database_writes': False, 'dump_exported': False, 'enterprise_source_bodies_exported': False}
            write(root, 'evidence-files.json', receipt)
            verifier.verify_file_manifest(root)
            for edit in ('changed', 'missing', 'extra', 'scope'):
                (root / 'metadata.json').write_bytes(body)
                (root / 'extra.py').unlink(missing_ok=True)
                write(root, 'evidence-files.json', receipt)
                if edit == 'changed': (root / 'metadata.json').write_bytes(b'different')
                elif edit == 'missing': (root / 'metadata.json').unlink()
                elif edit == 'extra': (root / 'extra.py').write_text('raise RuntimeError("must never execute")')
                else: write(root, 'evidence-files.json', dict(receipt, database_writes=True))
                with self.subTest(edit=edit), self.assertRaises(verifier.base.EvidenceError):
                    verifier.verify_file_manifest(root)

    def test_original_counters_and_nonstock_business_change_fail_before_any_normalizer(self):
        before = {'business_%04d' % index: {'rows': 1, 'hash': str(index)} for index in range(921)}
        before.update({'ir_sequence_%04d' % index: {'rows': 1, 'hash': '{"last_value":1}'} for index in range(140)})
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            write(root, 'cerro-reference/business-before.json', before)
            module = verifier.OWN_MODULES[0]
            source = {module + '/__manifest__.py': repr({'version': '18.0.1.0.0'}).encode()}
            write(root, 'cerro-reference/version-admission.json', {module: {
                'original': '18.0.1.0.0', 'candidate': '18.0.1.0.0', 'downgrade': False}})
            for edit in ('counter', 'business', 'new_table'):
                after = deepcopy(before)
                if edit == 'counter': after['ir_sequence_0000']['hash'] = '{"last_value":2}'
                elif edit == 'business': after['business_0000']['hash'] = 'changed'
                else: after['extra_table'] = {'rows': 0, 'hash': ''}
                write(root, 'cerro-reference/business-after-upgrade.json', after)
                write(root, 'cerro-reference/business-after.json', after)
                with patch.object(verifier.treasury, 'verify') as normalizer:
                    with self.subTest(edit=edit), self.assertRaises(verifier.base.EvidenceError):
                        verifier.verify_preservation(root, source, {}, Path(folder))
                    normalizer.assert_not_called()

    def test_focused_old_count_or_unmeasured_module_graph_is_not_acceptance(self):
        receipt = {'mode': 'community', 'profile': 'simpledigital', 'accelerated': True,
            'custody_grouping': True, 'multifront': True, 'focused_development_pass': False,
            'expected_test_count': 576, 'package_files': 0, 'counts': {'installed': 123, 'enterprise': 0}}
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            write(root, 'community/source-files.json', {})
            receipt['source_files_sha256'] = verifier.sha((root / 'community/source-files.json').read_bytes())
            graph = {'source': 'independently_measured_by_coordinator', 'community': {'installed': 123, 'enterprise': 0}}
            write(root, 'graph-admission.json', graph)
            for edit in ('focused', 'old_tests', 'cold_tests', 'wrong_graph', 'unmeasured_graph'):
                changed = deepcopy(receipt)
                write(root, 'graph-admission.json', graph)
                if edit == 'focused': changed['focused_development_pass'] = True
                elif edit == 'old_tests': changed['expected_test_count'] = 473
                elif edit == 'cold_tests': changed['expected_test_count'] = 25
                elif edit == 'wrong_graph': changed['counts']['installed'] = 124
                else: write(root, 'graph-admission.json', dict(graph, source='copied_from_this_receipt'))
                write(root, 'community/passed.json', changed)
                with self.subTest(edit=edit), self.assertRaises(verifier.base.EvidenceError):
                    verifier.verify_receipt(root, {}, {}, 'community')


if __name__ == '__main__':
    unittest.main()
