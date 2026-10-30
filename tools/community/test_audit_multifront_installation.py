"""Synthetic module metadata only; never connects to PostgreSQL or imports Odoo."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

import audit_multifront_installation as audit


def fixture_source(operational_extensions=False, quality_extension=False):
    root = Path(__file__).resolve().parents[2]
    source = {module + '/__manifest__.py': (root / module / '__manifest__.py').read_bytes()
              for module in audit.OWN_MODULES}
    name = 'tools/community/simpledigital_runtime_source.json'
    source[name] = (root / name).read_bytes()
    source[audit.PROVIDER + '/__manifest__.py'] = repr({'license': 'AGPL-3', 'version': '18.0.1.1.0',
        'depends': ['step_simpledigital_oca_base']}).encode()
    if operational_extensions:
        # Synthetic manifests test metadata policy only; they are never
        # presented as product source or database acceptance.
        source.update({name + '/__manifest__.py': repr({'license': 'LGPL-3', 'version': '18.0.1.0.0'}).encode()
            for name in audit.EXTENSION_MODULES})
    if quality_extension:
        source.update({name + '/__manifest__.py': (root / name / '__manifest__.py').read_bytes()
            for name in audit.QUALITY_MODULES})
    return source


def fixture(mode, operational_extensions=False, quality_extension=False):
    root = fixture_source(operational_extensions, quality_extension)
    plan = audit.plan(root, mode, operational_extensions=operational_extensions, quality_extension=quality_extension)
    rows = [{'name': name, 'latest_version': spec['version'], 'license': spec['license'], 'state': 'installed'}
            for name, spec in plan['required'].items()]
    if mode != 'community':
        rows += [{'name': name, 'latest_version': '18.0.1.0.0', 'license': 'OEEL-1', 'state': 'installed'}
                 for name in sorted(audit.NATIVE_ENGINES)]
        rows += [{'name': 'synthetic_EE_%s' % index, 'latest_version': '18.0.1.0.0', 'license': 'OEEL-1', 'state': 'installed'}
                 for index in range(138)]
    database = ('COMMUNITY_PAYROLL_API_' if mode == 'community' else 'MANAGEMENT_QA_CERRO_PAYROLL_API_') + 'SYNTHETIC'
    passed = {'mode': mode, 'multifront': True, 'focused_development_pass': False,
              'expected_test_count': (audit.QUALITY_TESTS if quality_extension else audit.EXTENSION_TESTS if operational_extensions else audit.EXPECTED_TESTS)[mode], 'database': database, 'writes_to_source': False,
              'counts': {'installed': len(rows), 'enterprise': 0 if mode == 'community' else 140}}
    if operational_extensions:
        passed['operational_extensions'] = True
    if quality_extension:
        passed['quality_extension'] = True
    metadata = {'database': database, 'transaction_read_only': 'on', 'installed': rows, 'pending': [],
                'payslip_models': [{'id': 555, 'model': 'hr.payslip'}], 'payslip_table_exists': True,
                'payslip_model_aliases': [{'id': 777, 'module': 'payroll' if mode == 'community' else 'hr_payroll',
                    'name': 'model_hr_payslip', 'model': 'ir.model', 'res_id': 555, 'noupdate': False}]}
    return root, passed, metadata


class MultifrontInstallationCase(unittest.TestCase):
    def test_critical_receipt_requires_its_explicit_generation_and_exact_count(self):
        for mode in ('community', 'cerro-reference'):
            source, passed, metadata = fixture(mode, True, True)
            passed = dict(passed, critical_extension=True, expected_test_count=audit.CRITICAL_TESTS[mode])
            proof = audit.audit(lambda db, query: json.dumps(metadata), mode, source, passed,
                operational_extensions=True, quality_extension=True, critical_extension=True)
            audit.verify(proof, mode, source, passed, operational_extensions=True,
                quality_extension=True, critical_extension=True)
            for altered in (dict(passed, critical_extension=False),
                            dict(passed, expected_test_count=audit.QUALITY_TESTS[mode])):
                with self.assertRaises(ValueError):
                    audit.verify(proof, mode, source, altered, operational_extensions=True,
                        quality_extension=True, critical_extension=True)
            with self.assertRaises(ValueError):
                audit.verify(proof, mode, source, passed, operational_extensions=True, quality_extension=True)

    def test_quality_profile_requires_exact_thirtythree_and_distinct_oca_native_providers(self):
        for mode, total in (('community', 31), ('cerro-reference', 27)):
            source, passed, metadata = fixture(mode, True, True)
            proof = audit.audit(lambda db, query: json.dumps(metadata), mode, source, passed,
                operational_extensions=True, quality_extension=True)
            self.assertEqual(len(audit.owned_modules(True, True)), 33)
            self.assertEqual(proof['plan']['owned_required'], 26)
            self.assertEqual(len(proof['plan']['required']), total)
            self.assertEqual(proof['plan']['quality_vendor_pin'], audit.QUALITY_PIN)
            self.assertEqual(audit.QUALITY_PROVIDER in proof['plan']['required'], mode == 'community')
            self.assertIn('step_quality_contracts', proof['plan']['required'])
            for count in (576, 391, 637, 437, 646, 441, passed['expected_test_count'] + 1):
                if count == passed['expected_test_count']: continue
                calls = []
                with self.subTest(mode=mode, count=count), self.assertRaises(ValueError):
                    audit.audit(lambda *args: calls.append(args), mode, source, dict(passed, expected_test_count=count),
                        operational_extensions=True, quality_extension=True)
                self.assertEqual(calls, [])
            legacy = dict(passed, quality_extension=False, expected_test_count=audit.EXTENSION_TESTS[mode])
            with self.assertRaisesRegex(ValueError, 'Quality modules require their explicit profile'):
                audit.audit(lambda *args: json.dumps(metadata), mode, source, legacy, operational_extensions=True)
        for operational, quality in ((False, True), (1, True), (True, 1)):
            with self.assertRaises(ValueError): audit.owned_modules(operational, quality)

    def test_quality_missing_tampered_and_cross_mode_provider_cannot_be_hidden_by_counts(self):
        for mode in audit.EXCLUDED:
            source, passed, metadata = fixture(mode, True, True)
            for change in ('missing', 'version', 'license', 'cross_provider', 'profile'):
                altered, receipt = deepcopy(metadata), deepcopy(passed)
                name = audit.QUALITY_PROVIDER if mode == 'community' else 'step_qa_native_reference'
                row = next(row for row in altered['installed'] if row['name'] == name)
                if change == 'missing': altered['installed'].remove(row)
                elif change == 'version': row['latest_version'] = '18.0.0.0.0'
                elif change == 'license': row['license'] = 'LGPL-3'
                elif change == 'cross_provider': altered['installed'].append({'name':
                    'step_qa_native_reference' if mode == 'community' else audit.QUALITY_PROVIDER,
                    'latest_version': audit.QUALITY_VERSION, 'license': 'AGPL-3', 'state': 'installed'})
                else: receipt['quality_extension'] = False
                receipt['counts']['installed'] = len(altered['installed'])
                with self.subTest(mode=mode, change=change), self.assertRaises(ValueError):
                    audit.audit(lambda *args: json.dumps(altered), mode, source, receipt,
                        operational_extensions=True, quality_extension=True)

    def test_operational_profile_requires_exact_30_owned_and_mode_specific_provider(self):
        for mode in audit.EXCLUDED:
            source, passed, metadata = fixture(mode, True)
            proof = audit.audit(lambda db, query: json.dumps(metadata), mode, source, passed, operational_extensions=True)
            self.assertTrue(proof['operational_extensions'])
            self.assertEqual(proof['plan']['owned_required'], 24)
            self.assertEqual(len(proof['plan']['required']), 28 if mode == 'community' else 25)
            self.assertEqual(audit.verify(proof, mode, source, passed, operational_extensions=True), proof['observed'])
            self.assertIn('step_payroll_original_report', proof['plan']['required'])
            self.assertEqual('payroll_contract_advantages' in proof['plan']['required'], mode == 'community')
            for count in (576, 391, 637, 437, passed['expected_test_count'] + 1):
                if count == passed['expected_test_count']:
                    continue
                calls = []
                changed = dict(passed, expected_test_count=count)
                with self.assertRaises(ValueError):
                    audit.audit(lambda db, sql: calls.append(sql), mode, source, changed, operational_extensions=True)
                self.assertEqual(calls, [])
            with self.assertRaises(ValueError):
                audit.audit(lambda db, sql: json.dumps(metadata), mode, source, passed)
            # A forged H label/count cannot hide the actual extension modules.
            legacy = dict(passed, expected_test_count=audit.EXPECTED_TESTS[mode], operational_extensions=False)
            with self.assertRaisesRegex(ValueError, 'require their explicit profile'):
                audit.audit(lambda db, sql: json.dumps(metadata), mode, source, legacy)

    def test_operational_vendor_absence_wrong_version_and_cross_provider_fail_closed(self):
        for mode in audit.EXCLUDED:
            source, passed, metadata = fixture(mode, True)
            for edit in ('missing', 'wrong_version', 'wrong_license', 'foreign_provider', 'hidden_profile'):
                changed, receipt = deepcopy(metadata), deepcopy(passed)
                target = 'payroll_contract_advantages' if mode == 'community' else 'step_payroll_benefits_native_reference'
                row = next(row for row in changed['installed'] if row['name'] == target)
                if edit == 'missing': changed['installed'].remove(row)
                elif edit == 'wrong_version': row['latest_version'] = '18.0.0.0.0'
                elif edit == 'wrong_license': row['license'] = 'AGPL-3'
                elif edit == 'foreign_provider': changed['installed'].append({'name':
                    'step_payroll_benefits_native_reference' if mode == 'community' else 'payroll_contract_advantages',
                    'latest_version': '18.0.1.0.0', 'license': 'LGPL-3', 'state': 'installed'})
                else: receipt['operational_extensions'] = False
                receipt['counts']['installed'] = len(changed['installed'])
                with self.subTest(mode=mode, edit=edit), self.assertRaises(ValueError):
                    audit.audit(lambda db, query: json.dumps(changed), mode, source, receipt, operational_extensions=True)

    def test_mode_plans_cover_new_treasury_t138_and_caf_versions(self):
        root = fixture_source()
        for mode, version_count in (('community', 25), ('cerro-reference', 23)):
            expected = audit.plan(root, mode)
            self.assertEqual(expected['owned_required'], 22)
            self.assertEqual(len(expected['required']), version_count)
            for name in ('step_account_treasury', 'step_treasury_community_reports', 'step_account_treasury_reports',
                         'step_hr_contract_days', 'step_l10n_cl_edi_core', 'step_l10n_cl_caf_custody_core'):
                self.assertIn(name, expected['required'])
            self.assertEqual('step_hr_contract_days_oca' in expected['required'], mode == 'community')
            self.assertEqual('step_l10n_cl_caf_storage' in expected['required'], mode == 'community')
            self.assertEqual('step_l10n_cl_caf_native_reference' in expected['required'], mode != 'community')

    def test_readonly_callback_captures_actual_graph_and_keeps_modes_distinct(self):
        for mode in audit.EXCLUDED:
            root, passed, metadata = fixture(mode)
            calls = []
            def sql(database, statement):
                calls.append((database, statement))
                return json.dumps(metadata)
            proof = audit.audit(sql, mode, root, passed)
            self.assertEqual(audit.verify(proof, mode, root, passed), proof['observed'])
            self.assertEqual(calls, [(passed['database'], audit.QUERY)])
            self.assertIn('READ ONLY', calls[0][1])
            self.assertNotIn('FROM hr_payslip', calls[0][1])
            for command in ('UPDATE ', 'DELETE ', 'INSERT ', 'ALTER ', 'CREATE ', 'DROP '):
                self.assertNotIn(command, calls[0][1])
            self.assertEqual(proof['observed']['community_engine_installed'], mode == 'community')
            self.assertEqual(proof['observed']['native_engine_retained'], mode != 'community')
            self.assertFalse(proof['database_writes'])

    def test_missing_old_or_wrong_version_license_and_forbidden_provider_rejected(self):
        for mode in audit.EXCLUDED:
            root, passed, metadata = fixture(mode)
            for edit in ('missing', 'old_version', 'license', 'forbidden', 'pending'):
                changed = deepcopy(metadata)
                if edit == 'missing': changed['installed'].pop(0)
                elif edit == 'old_version': changed['installed'][0]['latest_version'] = '18.0.0.0.0'
                elif edit == 'license': changed['installed'][0]['license'] = 'OEEL-1'
                elif edit == 'forbidden': changed['installed'].append({'name': sorted(audit.EXCLUDED[mode])[0],
                    'latest_version': '18.0.1.0.0', 'license': 'LGPL-3', 'state': 'installed'})
                else: changed['pending'].append(dict(changed['installed'][0], state='to upgrade'))
                # Keep receipt counts consistent to exercise the version/root
                # guards rather than just rejecting a count mismatch.
                receipt = deepcopy(passed)
                receipt['counts'] = {'installed': len(changed['installed']),
                    'enterprise': sum(row['license'] == 'OEEL-1' for row in changed['installed'])}
                with self.subTest(mode=mode, edit=edit), self.assertRaises(ValueError):
                    audit.audit(lambda db, query: json.dumps(changed), mode, root, receipt)

    def test_model_alias_foreign_database_readwrite_and_diagnostic_pass_fail_closed(self):
        root, passed, metadata = fixture('community')
        for edit in ('table', 'model', 'alias', 'database', 'readwrite', 'focused'):
            changed, receipt = deepcopy(metadata), deepcopy(passed)
            if edit == 'table': changed['payslip_table_exists'] = False
            elif edit == 'model': changed['payslip_models'].append({'id': 556, 'model': 'hr.payslip'})
            elif edit == 'alias': changed['payslip_model_aliases'][0]['res_id'] = 556
            elif edit == 'database': changed['database'] = 'OTHER_PRIVATE_DATABASE'
            elif edit == 'readwrite': changed['transaction_read_only'] = 'off'
            else: receipt['focused_development_pass'] = True
            with self.subTest(edit=edit), self.assertRaises(ValueError):
                audit.audit(lambda db, query: json.dumps(changed), 'community', root, receipt)

    def test_entire_required_manifest_plan_is_sealed_against_source_changes(self):
        root, passed, metadata = fixture('community')
        proof = audit.audit(lambda db, query: json.dumps(metadata), 'community', root, passed)
        changed = deepcopy(proof)
        changed['plan']['required']['step_hr_contract_days']['version'] = '18.0.0.0.0'
        with self.assertRaises(ValueError):
            audit.verify(changed, 'community', root, passed)
        changed = deepcopy(proof)
        changed['observed']['historical_conversion'] = True
        with self.assertRaises(ValueError):
            audit.verify(changed, 'community', root, passed)


if __name__ == '__main__':
    unittest.main()
