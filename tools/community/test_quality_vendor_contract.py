"""Pure source custody tests; no network, database, ORM or artifact execution."""
import base64
from copy import deepcopy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import quality_vendor_contract as vendor


def fixture(*, license='AGPL-3', dependencies=None):
    manifest = {'version': vendor.VERSION, 'license': license,
        'depends': vendor.DEPENDENCIES if dependencies is None else dependencies}
    files = {vendor.MODULE + '/__manifest__.py': repr(manifest).encode(),
        vendor.MODULE + '/models/inspection.py': b'raise RuntimeError("artifact must not execute")\n'}
    trees = {}

    def tree(entries):
        body = b''.join(mode + b' ' + name.encode() + b'\0' + bytes.fromhex(oid)
            for mode, name, oid in sorted(entries, key=lambda entry: entry[1]))
        oid = vendor.git_object_oid('tree', body)
        trees[oid] = base64.b64encode(body).decode()
        return oid, body

    models, _ = tree([(b'100644', 'inspection.py', vendor.git_object_oid('blob', files[vendor.MODULE + '/models/inspection.py']))])
    module, _ = tree([(b'100644', '__manifest__.py', vendor.git_object_oid('blob', files[vendor.MODULE + '/__manifest__.py'])),
        (b'40000', 'models', models)])
    root_id, root = tree([(b'40000', vendor.MODULE, module)])
    trees.pop(root_id)
    commit = ('tree ' + root_id + '\nauthor SYNTHETIC <synthetic@example.invalid> 0 +0000\n'
        'committer SYNTHETIC <synthetic@example.invalid> 0 +0000\n\nSynthetic source custody\n').encode()
    pin = vendor.git_object_oid('commit', commit)
    hashes, seal = vendor.fingerprint(files)
    proof = {'schema': 1, 'repository': vendor.REPOSITORY, 'oca_pin': pin, 'module': vendor.MODULE,
        'version': vendor.VERSION, 'license': vendor.LICENSE, 'dependencies': vendor.DEPENDENCIES,
        'commit_object_b64': base64.b64encode(commit).decode(), 'root_tree_object_b64': base64.b64encode(root).decode(),
        'trees_by_oid_b64': trees, 'source_files_sha256': hashes, 'source_files_fingerprint': seal,
        'file_count': len(files), 'vendor_sources_unmodified': True,
        'native_identity_converted': False, 'artifact_code_executed': False}
    return pin, proof, files


class QualityVendorContractCase(unittest.TestCase):
    def test_exact_public_commit_all_trees_blobs_and_fingerprint_without_execution(self):
        pin, proof, files = fixture()
        with patch.object(vendor, 'PIN', pin):
            result = vendor.verify(proof, files)
        self.assertEqual(result['file_count'], 2)
        self.assertTrue(result['all_blobs_bound_to_pinned_commit'])
        self.assertFalse(result['artifact_code_executed'])
        self.assertFalse(result['native_identity_converted'])
        with self.assertRaises(ValueError):
            vendor.verify(proof, files)

    def test_missing_extra_tampered_files_objects_and_scope_are_rejected(self):
        pin, proof, files = fixture()
        for mutation in ('missing', 'extra', 'changed_blob', 'missing_tree', 'seal', 'converted', 'pin'):
            altered, source = deepcopy(proof), dict(files)
            if mutation == 'missing': source.pop(next(iter(source)))
            elif mutation == 'extra': source[vendor.MODULE + '/extra.py'] = b'no'
            elif mutation == 'changed_blob': source[vendor.MODULE + '/models/inspection.py'] += b'# changed'
            elif mutation == 'missing_tree': altered['trees_by_oid_b64'].pop(next(iter(altered['trees_by_oid_b64'])))
            elif mutation == 'seal': altered['source_files_fingerprint'] = '0' * 64
            elif mutation == 'converted': altered['native_identity_converted'] = True
            else: altered['oca_pin'] = '0' * 40
            with self.subTest(mutation=mutation), patch.object(vendor, 'PIN', pin), self.assertRaises((ValueError, KeyError)):
                vendor.verify(altered, source)

    def test_even_hash_bound_enterprise_or_changed_dependencies_are_refused(self):
        for options in ({'license': 'OEEL-1'}, {'dependencies': ['quality_control']}):
            pin, proof, files = fixture(**options)
            with patch.object(vendor, 'PIN', pin), self.assertRaisesRegex(ValueError, 'license/version/dependencies'):
                vendor.verify(proof, files)

    def test_new_separate_runtime_and_private_proof_are_exclusive_and_reverified(self):
        pin, proof, files = fixture()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output, report = root / 'addons', root / 'proof.json'
            with patch.object(vendor, 'PIN', pin), patch.object(vendor, 'capture', return_value=(proof, files)):
                result = vendor.materialize(root, output, report)
                self.assertEqual(result['file_count'], 2)
                self.assertEqual(json.loads(report.read_text()), proof)
                self.assertEqual({path.relative_to(output).as_posix(): path.read_bytes()
                    for path in output.rglob('*') if path.is_file()}, files)
                if os.name != 'nt':
                    self.assertEqual(report.stat().st_mode & 0o777, 0o600)
                    self.assertEqual(output.stat().st_mode & 0o777, 0o755)
                    self.assertTrue(all(path.stat().st_mode & 0o777 == 0o644
                        for path in output.rglob('*') if path.is_file()))
                with self.assertRaises(ValueError):
                    vendor.materialize(root, output, report)
                with self.assertRaises(ValueError):
                    vendor.materialize(root, root / 'other', root / 'other' / 'proof.json')


if __name__ == '__main__':
    unittest.main()
