"""Pure pin, byte-custody and test-scope negatives; no Odoo or database access."""
import base64
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import build_numeric_input_engine as numeric
import verify_original_contracts_evidence as verifier


def git_fixture(files):
    """Make real binary Git objects for a deliberately synthetic test commit."""
    objects = {}
    def tree(values):
        entries = []
        children = {}
        for name, body in values.items():
            head, separator, tail = name.partition('/')
            if separator:
                children.setdefault(head, {})[tail] = body
            else:
                entries.append((head, b'100644', verifier.git_object_oid('blob', body)))
        for name, children_files in children.items():
            entries.append((name, b'40000', tree(children_files)))
        raw = b''.join(mode + b' ' + name.encode() + b'\0' + bytes.fromhex(oid)
            for name, mode, oid in sorted(entries))
        oid = verifier.git_object_oid('tree', raw)
        objects[oid] = raw
        return oid
    payroll = tree(files)
    root = b'40000 payroll\0' + bytes.fromhex(payroll)
    root_oid = verifier.git_object_oid('tree', root)
    commit = ('tree ' + root_oid + '\nauthor Synthetic <synthetic@example.invalid> 0 +0000\n'
        'committer Synthetic <synthetic@example.invalid> 0 +0000\n\nPure test fixture\n').encode()
    encode = lambda value: base64.b64encode(value).decode()
    return verifier.git_object_oid('commit', commit), {
        'commit_object_b64': encode(commit), 'root_tree_object_b64': encode(root),
        'trees_by_oid_b64': {oid: encode(body) for oid, body in objects.items()}}


class OriginalContractsEvidenceCase(unittest.TestCase):
    def engine_source(self):
        return {'__manifest__.py': b"{'license':'LGPL-3','data':[]}",
            numeric.FILE: b"from odoo import fields, models\nclass HrPayslipInput(models.Model):\n"
                b"    amount = fields.Float(\n        help='Exact source text'\n    )\n"
                b"    code = fields.Char(required=True)\n",
            'models/__init__.py': b'from . import hr_payslip_input\n'}

    def test_pinned_git_objects_bind_all_original_files_and_reject_tampering(self):
        source = self.engine_source()
        pin, proof = git_fixture(source)
        with patch.object(numeric, 'PIN', pin):
            result = verifier.verify_engine_git(proof, source)
            self.assertEqual(result['payroll_blob_count'], len(source))
            for mutation in ('blob', 'missing', 'root', 'commit', 'extra_tree'):
                changed, receipt = dict(source), deepcopy(proof)
                if mutation == 'blob':
                    changed[numeric.FILE] += b'# altered\n'
                elif mutation == 'missing':
                    changed.pop('models/__init__.py')
                elif mutation in ('root', 'commit'):
                    key = mutation + '_tree_object_b64' if mutation == 'root' else 'commit_object_b64'
                    receipt[key] = base64.b64encode(b'altered').decode()
                else:
                    raw = b'100644 other\0' + bytes(20)
                    receipt['trees_by_oid_b64'][verifier.git_object_oid('tree', raw)] = base64.b64encode(raw).decode()
                with self.subTest(mutation=mutation), self.assertRaises(verifier.base.EvidenceError):
                    verifier.verify_engine_git(receipt, changed)

    def test_numeric_derivation_replays_only_keyword_and_artifact_python_is_inert(self):
        source = self.engine_source()
        pin, proof = git_fixture(source)
        trusted = {'tools/community/build_numeric_input_engine.py': Path(numeric.__file__).read_bytes()}
        with tempfile.TemporaryDirectory() as folder, patch.object(numeric, 'PIN', pin):
            root = Path(folder)
            candidate = numeric.plan(source)
            for name, files in (('engine-original', source), ('engine-candidate', candidate)):
                for relative, body in files.items():
                    path = root / name / 'payroll' / relative
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(body)
            (root / 'engine-git-proof.json').write_text(json.dumps(proof))
            (root / numeric.REPORT).write_text(json.dumps(numeric.report_for(source, candidate)))
            self.assertTrue(verifier.verify_engine(root, trusted)['first_initialization_numeric'])
            path = root / 'engine-candidate/payroll' / numeric.FILE
            path.write_bytes(path.read_bytes() + b"\nraise RuntimeError('Artifact must never execute')\n")
            with self.assertRaisesRegex(verifier.base.EvidenceError, 'one supported keyword'):
                verifier.verify_engine(root, trusted)
            path.write_bytes(candidate[numeric.FILE])
            report = json.loads((root / numeric.REPORT).read_text())
            report['financial_certified'] = True
            report.pop('seal_sha256')
            report['seal_sha256'] = numeric.seal(report)
            (root / numeric.REPORT).write_text(json.dumps(report))
            with self.assertRaisesRegex(verifier.base.EvidenceError, 'seal or no-conversion'):
                verifier.verify_engine(root, trusted)

    def test_packet_changes_are_limited_to_six_new_API_files_and_exact_git(self):
        own = {name + '/__manifest__.py': b'original' for name in verifier.base.OWN_MODULES}
        own.update({'step_payroll_oca_api/old-%s.py' % index: b'original' for index in range(284)})
        previous = {name: verifier.sha(body) for name, body in own.items()}
        previous.update({'l10n_cl_simpledigital_payroll/file-%s.py' % index: verifier.sha(b'provider') for index in range(49)})
        self.assertEqual(len(previous), 355)
        own.update({'step_payroll_oca_api/new-%s.py' % index: b'new' for index in range(6)})
        current = dict(previous)
        current.update({name: verifier.sha(body) for name, body in own.items()})
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            def write_packet(relative, value):
                path = root / relative
                path.parent.mkdir(exist_ok=True)
                path.write_text(json.dumps(value))
            write_packet('baseline-F/source-files.json', previous)
            write_packet('community/source-files.json', current)
            write_packet('cerro-reference/source-files.json', current)
            verifier.verify_packets(root, own)
            name = 'step_simpledigital_oca_base/__manifest__.py'
            own[name], current[name] = b'changed', verifier.sha(b'changed')
            for mode in ('community', 'cerro-reference'):
                write_packet(mode + '/source-files.json', current)
            with self.assertRaisesRegex(verifier.base.EvidenceError, 'outside the API block'):
                verifier.verify_packets(root, own)

    def test_all_25_real_case_names_must_execute_once_and_are_not_12_or_460(self):
        source, lines = {}, []
        for filename, classname, count in verifier.TEST_CLASSES:
            methods = ['test_fixture_%s' % index for index in range(count)]
            source[filename] = ('class ' + classname + ':\n' + ''.join('    def %s(self): pass\n' % name for name in methods)).encode()
            lines.extend('Starting %s.%s ...' % (classname, name) for name in methods)
        self.assertEqual(sum(verifier.verify_test_methods(source, '\n'.join(lines)).values()), 25)
        with self.assertRaisesRegex(verifier.base.EvidenceError, 'exactly once'):
            verifier.verify_test_methods(source, '\n'.join(lines[:-1]))
        with self.assertRaisesRegex(verifier.base.EvidenceError, 'exactly once'):
            verifier.verify_test_methods(source, '\n'.join(lines + lines[:1]))
        for count in (12, 37, 460):
            with self.assertRaises(verifier.base.EvidenceError):
                verifier.base.test_result(['0 failed, 0 error(s) of %s tests' % count], 25)


if __name__ == '__main__':
    unittest.main()
