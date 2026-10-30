"""Synthetic Git object graph tests; no external repository/database/ORM."""
import base64
from copy import deepcopy
import unittest
from unittest.mock import patch

import oca_vendor_contract as vendor


def fixture(*, advantages_license='LGPL-3'):
    files, trees, roots = {}, {}, {}
    for module, version in vendor.VERSIONS.items():
        count = 144 if module == 'payroll' else 2
        values = {'__manifest__.py': repr({'license': advantages_license if module == 'payroll_contract_advantages' else 'LGPL-3',
            'version': version}).encode()}
        values.update({'synthetic_%03d.py' % index: b'raise RuntimeError("artifact must never execute")\n'
            for index in range(count - 1)})
        files.update({module + '/' + name: body for name, body in values.items()})
        body = b''.join(b'100644 ' + name.encode() + b'\0' + bytes.fromhex(vendor.git_object_oid('blob', value))
            for name, value in sorted(values.items()))
        oid = vendor.git_object_oid('tree', body)
        trees[oid] = base64.b64encode(body).decode()
        roots[module] = oid
    body = b''.join(b'40000 ' + name.encode() + b'\0' + bytes.fromhex(oid) for name, oid in sorted(roots.items()))
    commit = ('tree ' + vendor.git_object_oid('tree', body) + '\nauthor SYNTHETIC <synthetic@example.invalid> 0 +0000\n'
        'committer SYNTHETIC <synthetic@example.invalid> 0 +0000\n\nSynthetic policy test only\n').encode()
    pin = vendor.git_object_oid('commit', commit)
    proof = {'schema': 1, 'oca_pin': pin, 'modules': sorted(vendor.VERSIONS),
        'commit_object_b64': base64.b64encode(commit).decode(), 'root_tree_object_b64': base64.b64encode(body).decode(),
        'trees_by_oid_b64': trees}
    return pin, proof, files


class OCAVendorContractCase(unittest.TestCase):
    def test_exact_three_git_subtrees_and_all_blobs_are_bound_without_executing_them(self):
        pin, proof, files = fixture()
        with patch.object(vendor, 'PIN', pin):
            result = vendor.verify(proof, files)
        self.assertEqual(result['module_files'], {'payroll': 144, 'payroll_account': 2, 'payroll_contract_advantages': 2})
        self.assertTrue(result['all_blobs_bound_to_pinned_commit'])
        self.assertFalse(result['extra_derivation'])
        self.assertFalse(result['artifact_code_executed'])
        # Synthetic commit cannot be substituted for the actual constant pin.
        with self.assertRaises(ValueError):
            vendor.verify(proof, files)

    def test_advantages_missing_changed_blob_pin_and_extra_tree_are_rejected(self):
        pin, proof, files = fixture()
        for edit in ('missing_advantage', 'blob', 'pin', 'tree', 'surplus', 'extra_module'):
            changed, bodies = deepcopy(proof), dict(files)
            if edit == 'missing_advantage': bodies.pop('payroll_contract_advantages/synthetic_000.py')
            elif edit == 'blob': bodies['payroll_contract_advantages/synthetic_000.py'] += b'# changed\n'
            elif edit == 'pin': changed['oca_pin'] = '0' * 40
            elif edit == 'tree': changed['trees_by_oid_b64'].pop(next(iter(changed['trees_by_oid_b64'])))
            elif edit == 'surplus': changed['trees_by_oid_b64'][vendor.git_object_oid('tree', b'')] = ''
            else: bodies['unreviewed_addon/__manifest__.py'] = b'{}'
            with self.subTest(edit=edit), patch.object(vendor, 'PIN', pin), self.assertRaises(ValueError):
                vendor.verify(changed, bodies)

    def test_even_pinned_git_does_not_admit_an_enterprise_license(self):
        pin, proof, files = fixture(advantages_license='OEEL-1')
        with patch.object(vendor, 'PIN', pin), self.assertRaisesRegex(ValueError, 'license/version'):
            vendor.verify(proof, files)


if __name__ == '__main__':
    unittest.main()
