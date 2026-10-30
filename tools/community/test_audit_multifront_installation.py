"""Synthetic module metadata only; never connects to PostgreSQL or imports Odoo."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

import audit_multifront_installation as audit


def fixture_source():
    root = Path(__file__).resolve().parents[2]
    source = {module + '/__manifest__.py': (root / module / '__manifest__.py').read_bytes()
              for module in audit.OWN_MODULES}
    name = 'tools/community/simpledigital_runtime_source.json'
    source[name] = (root / name).read_bytes()
    source[audit.PROVIDER + '/__manifest__.py'] = repr({'license': 'AGPL-3', 'version': '18.0.1.1.0',
        'depends': ['step_simpledigital_oca_base']}).encode()
    return source


def fixture(mode):
    root = fixture_source()
    plan = audit.plan(root, mode)
    rows = [{'name': name, 'latest_version': spec['version'], 'license': spec['license'], 'state': 'installed'}
            for name, spec in plan['required'].items()]
    if mode != 'community':
        rows += [{'name': name, 'latest_version': '18.0.1.0.0', 'license': 'OEEL-1', 'state': 'installed'}
                 for name in sorted(audit.NATIVE_ENGINES)]
        rows += [{'name': 'synthetic_EE_%s' % index, 'latest_version': '18.0.1.0.0', 'license': 'OEEL-1', 'state': 'installed'}
                 for index in range(138)]
    database = ('COMMUNITY_PAYROLL_API_' if mode == 'community' else 'MANAGEMENT_QA_CERRO_PAYROLL_API_') + 'SYNTHETIC'
    passed = {'mode': mode, 'multifront': True, 'focused_development_pass': False,
              'expected_test_count': audit.EXPECTED_TESTS[mode], 'database': database, 'writes_to_source': False,
              'counts': {'installed': len(rows), 'enterprise': 0 if mode == 'community' else 140}}
    metadata = {'database': database, 'transaction_read_only': 'on', 'installed': rows, 'pending': [],
                'payslip_models': [{'id': 555, 'model': 'hr.payslip'}], 'payslip_table_exists': True,
                'payslip_model_aliases': [{'id': 777, 'module': 'payroll' if mode == 'community' else 'hr_payroll',
                    'name': 'model_hr_payslip', 'model': 'ir.model', 'res_id': 555, 'noupdate': False}]}
    return root, passed, metadata


class MultifrontInstallationCase(unittest.TestCase):
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
