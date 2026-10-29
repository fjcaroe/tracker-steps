"""Pure provenance checks; synthetic evidence is never an Odoo test result."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import validate_payroll_admission_upgrade as runner
import verify_payroll_admission_evidence as verifier


def sha(blob):
    return hashlib.sha256(blob).hexdigest()


def synthetic_package():
    modules = ['payroll', 'payroll_account', *runner.VERSIONS, 'owned_fixture']
    modules += ['vendor_' + str(i) for i in range(90)]
    package = {name: {'legacy': {'__manifest__.py': 'a' * 64},
                      'candidate': {'__manifest__.py': 'a' * 64}} for name in modules}
    source, current, baseline = {}, {}, {}
    for name, values in runner.VERSIONS.items():
        content = repr({'version': values[1], 'license': 'LGPL-3'}).encode()
        source[name + '/__manifest__.py'] = content
        current[name + '/__manifest__.py'] = sha(content)
        baseline[name + '/__manifest__.py'] = 'a' * 64
        package[name]['candidate'] = {'__manifest__.py': sha(content)}
    baseline['owned_fixture/__manifest__.py'] = 'a' * 64
    consumers = {'owned_fixture/__manifest__.py': 'b' * 64}
    package['owned_fixture']['legacy']['__manifest__.py'] = 'b' * 64
    package['owned_fixture']['candidate']['__manifest__.py'] = 'b' * 64
    return package, baseline, consumers, current, source


def synthetic_closed_fixture(paid=None):
    seed = dict(actor=50, company=70, contract=80, analytic=90, slip=100, day=110,
        unpaid_day=111, unpaid_type=120, structure=130, move=140, rule=150,
        normal_actor=True, real_oca_engine=True, synthetic_fixture_only=True,
        synthetic_paid_marker=True, payment_workflow_certified=False,
        confirmation_uses_existing_oca_draft_option=True, current_wage_changed_after_closure=True,
        synthetic_paid_marker_original_sql_value=paid, draft_amounts={'basic_wage': 800123},
        draft_day_values={'amount': 53333, 'is_paid': True},
        unpaid_day_values={'amount': 0, 'is_paid': False})
    seed['raw_rows'] = {
        'hr_payslip': [dict(id=100, employee_id=60, contract_id=80, company_id=70,
            move_id=140, state='done', paid=True, step_history_locked=True, basic_wage=800123)],
        'hr_contract': [dict(id=80, wage=1200000)],
        'hr_payslip_worked_days': [dict(id=110, payslip_id=100, amount=53333, is_paid=True),
            dict(id=111, payslip_id=100, amount=0, is_paid=False, work_entry_type_id=120)],
        'relations': {'hr_payroll_structure_hr_work_entry_type_rel': [
            dict(hr_payroll_structure_id=130, hr_work_entry_type_id=120)]},
        'account_move': [dict(id=140, state='posted')],
        'account_move_line': [dict(id=141, move_id=140, debit=800123, credit=0),
                              dict(id=142, move_id=140, debit=0, credit=800123)],
        'hr_payslip_line': [dict(id=160 + i, slip_id=100, salary_rule_id=150 + i,
            note='Synthetic original line', analytic_account_id=90, code=code)
            for i, code in enumerate(('BASIC', 'GROSS', 'NET'))],
        'hr_salary_rule': [dict(id=150, note={'en_US': '<p>Synthetic original</p>'},
            analytic_account_id={'70': 90})]}
    proof = dict(database='COMMUNITY_PAYROLL_API_ADMISSION_UPGRADE_SYNTHETIC',
                 synthetic_paid_marker_original_sql_value=paid)
    marker = dict(synthetic_fixture_only=True, database=proof['database'], id=100, employee_id=60,
        contract_id=80, company_id=70, state='done', step_history_locked=True, paid=paid,
        original_not_paid_predicate_matches=paid is False, null_aware_predicate_matches=True)
    return seed, marker, proof


class AdmissionEvidenceCase(unittest.TestCase):
    def test_saved_inputs_requires_all_three_updated_packages(self):
        try:
            runner.configure_profile('saved-inputs')
            args = synthetic_package()
            self.assertEqual(len(args[0]), 96)
            self.assertEqual(verifier._verify_package(*args, runner), 4)
            package, baseline, consumers, current, source = synthetic_package()
            package['step_simpledigital_oca_security']['candidate'] = package['step_simpledigital_oca_security']['legacy']
            with self.assertRaises(AssertionError):
                verifier._verify_package(package, baseline, consumers, current, source, runner)
            package, *rest = synthetic_package()
            package.pop('vendor_0')
            with self.assertRaises(AssertionError): verifier._verify_package(package, *rest, runner)
        finally:
            runner.configure_profile('admission')

    def test_packet_checks_complete_legacy_consumer_override_and_current_git_addons(self):
        args = synthetic_package()
        self.assertEqual(verifier._verify_package(*args, runner), 3)
        for location in ('legacy', 'candidate'):
            package, *rest = synthetic_package()
            package['owned_fixture'][location]['__manifest__.py'] = 'c' * 64
            with self.assertRaises(AssertionError): verifier._verify_package(package, *rest, runner)
        package, baseline, consumers, current, source = synthetic_package()
        package['step_payroll_oca_api']['candidate']['unreviewed.py'] = 'c' * 64
        with self.assertRaises(AssertionError):
            verifier._verify_package(package, baseline, consumers, current, source, runner)
        package, baseline, consumers, current, source = synthetic_package()
        current['step_payroll_oca_api/unreviewed.py'] = 'c' * 64
        with self.assertRaises(AssertionError):
            verifier._verify_package(package, baseline, consumers, current, source, runner)

    def test_consumer_cannot_add_files_or_modules_outside_accepted_source(self):
        package, baseline, consumers, current, source = synthetic_package()
        consumers['owned_fixture/unreviewed.py'] = 'c' * 64
        with self.assertRaises(AssertionError):
            verifier._verify_package(package, baseline, consumers, current, source, runner)
        package, baseline, consumers, current, source = synthetic_package()
        package.pop('payroll')
        with self.assertRaises(AssertionError):
            verifier._verify_package(package, baseline, consumers, current, source, runner)

    def test_synthetic_closed_fixture_requires_real_stored_accounting_and_nullable_marker(self):
        for paid in (None, False):
            verifier._verify_fixture(*synthetic_closed_fixture(paid))
        for mutation in (
            lambda seed: seed['raw_rows']['account_move'][0].update(state='draft'),
            lambda seed: seed['raw_rows']['account_move_line'][0].update(debit=800124),
            lambda seed: seed['raw_rows']['hr_contract'][0].update(wage=800000),
            lambda seed: seed['raw_rows']['hr_payslip_worked_days'][1].update(amount=1),
            lambda seed: seed['raw_rows']['relations']['hr_payroll_structure_hr_work_entry_type_rel'].clear(),
            lambda seed: seed['raw_rows']['hr_salary_rule'][0].update(analytic_account_id={'70': 90.0}),
            lambda seed: seed['raw_rows']['hr_payslip_line'][0].update(note={'en_US': 'new master'}),
            lambda seed: seed.update(payment_workflow_certified=True),
        ):
            seed, marker, proof = synthetic_closed_fixture()
            mutation(seed)
            with self.assertRaises(AssertionError): verifier._verify_fixture(seed, marker, proof)
        for name, value in (('paid', True), ('id', 200), ('company_id', 200),
                            ('step_history_locked', False), ('null_aware_predicate_matches', False)):
            seed, marker, proof = synthetic_closed_fixture()
            marker[name] = value
            with self.assertRaises(AssertionError): verifier._verify_fixture(seed, marker, proof)

    def test_json_ambiguity_nonfinite_numbers_and_unsafe_paths_are_rejected(self):
        for blob in (b'{"counts":0,"counts":1}', b'{"value":NaN}', b'{"value":Infinity}', b'{"value":1e999}'):
            with self.assertRaises((ValueError, AssertionError)): verifier._json(blob)
        for name in ('../x', '/module/x', 'module/../x', 'module//x', 'module/./x', 'module\\x', 'single'):
            with self.assertRaises(AssertionError): verifier._packet({name: 'a' * 64})
        self.assertEqual(verifier._packet({'module/models/file.py': 'a' * 64}),
                         {'module': {'models/file.py': 'a' * 64}})

    def test_helper_is_loaded_from_repository_after_git_and_dependency_seal_without_writes(self):
        repo = Path(__file__).resolve().parents[2]
        source = {name: (repo / name).read_bytes() for name in (verifier.RUNNER, verifier.DEPENDENCY)}
        for normalize in (False, True):
            with tempfile.TemporaryDirectory() as temporary:
                folder = Path(temporary)
                for output, name in (('upgrade-probe.py', verifier.RUNNER),
                                     (Path(verifier.DEPENDENCY).name, verifier.DEPENDENCY)):
                    blob = source[name]
                    if normalize: blob = blob.replace(b'\r\n', b'\n').replace(b'\n', b'\r\n')
                    (folder / output).write_bytes(blob)
                seals = {path.name: sha(path.read_bytes()) for path in folder.iterdir()}
                (folder / 'probe-dependencies.json').write_text(json.dumps(seals))
                proof = dict(probe_dependencies_sha256=sha((folder / 'probe-dependencies.json').read_bytes()),
                    tool_sha256=seals['upgrade-probe.py'], helper_sha256=seals[Path(verifier.DEPENDENCY).name])
                original = {path.name: path.read_bytes() for path in folder.iterdir()}
                dont_write = sys.dont_write_bytecode
                with patch('subprocess.run', side_effect=AssertionError('External execution refused')):
                    loaded = verifier._load_versioned_helper(folder, source, proof)
                self.assertEqual(loaded.SOURCE_DB, runner.SOURCE_DB)
                self.assertEqual(original, {path.name: path.read_bytes() for path in folder.iterdir()})
                self.assertEqual(sys.dont_write_bytecode, dont_write)
                (folder / 'upgrade-probe.py').write_bytes(b'changed probe')
                with self.assertRaises(AssertionError): verifier._load_versioned_helper(folder, source, proof)


if __name__ == '__main__':
    unittest.main()
