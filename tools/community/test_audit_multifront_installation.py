"""Synthetic module metadata only; never connects to PostgreSQL or imports Odoo."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

import audit_multifront_installation as audit


def fixture_source(operational_extensions=False, quality_extension=False, critical_generation=None):
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
    if critical_generation in audit.GENERATION_VERSIONS:
        for module, version in audit.GENERATION_VERSIONS[critical_generation].items():
            name = module + '/__manifest__.py'
            manifest = __import__('ast').literal_eval(source[name].decode())
            manifest['version'] = version
            source[name] = repr(manifest).encode()
    return source


def fixture(mode, operational_extensions=False, quality_extension=False, critical_generation=None):
    root = fixture_source(operational_extensions, quality_extension, critical_generation)
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


def security_metadata(database, oid=7001):
    return {'database':database,'transaction_read_only':'on','default_transaction_read_only':'on',
        'table':{'schema':'public','name':'rule_group_rel','kind':'r'},
        'column':{'name':'group_id','sql_type':'integer','not_null':True},
        'models':[{'id':1,'model':'ir.rule'},{'id':2,'model':'res.groups'}],
        'fields':[{'id':3,'model':'ir.rule','name':'groups','ttype':'many2many','relation':'res.groups','store':True},
            {'id':4,'model':'res.groups','name':'rule_groups','ttype':'many2many','relation':'ir.rule','store':True}],
        'foreign_keys':[{'oid':oid,'name':audit.SECURITY_GROUP_FK_NAME,'source_columns':['group_id'],
            'target_schema':'public','target_table':'res_groups','target_columns':['id'],
            'on_delete':'r','on_update':'a','match':'s','validated':True,'deferrable':False,'deferred':False,
            'definition':'FOREIGN KEY (group_id) REFERENCES res_groups(id) ON DELETE RESTRICT'}]}


def security_capture(database, phase, oid=7001):
    return audit.capture_security_group_fk(lambda db,query:json.dumps(security_metadata(db,oid)),database,phase)


def security_boundary(database, mode):
    before=security_capture(database,'before-native-upgrade') if mode!='community' else None
    upgrade=security_capture(database,'after-native-upgrade',7002) if mode!='community' else None
    after=security_capture(database,'after-tests',7002)
    digest=lambda item:audit.sha(json.dumps(item,indent=2).encode()) if item else None
    return {'recorded_under_shared_environment_lease':True,'manual_security_ddl_performed_by_validator':False,
        'before_native_upgrade':before,'after_native_upgrade':upgrade,'after_tests':after,
        'before_native_upgrade_sha256':digest(before),'after_native_upgrade_sha256':digest(upgrade),
        'after_tests_sha256':digest(after)}


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

    def test_s_generation_binds_exact_source_versions_count_and_files_without_changing_r3(self):
        self.assertEqual(audit.critical_tests(True), {'community': 665, 'cerro-reference': 457})
        self.assertEqual(audit.critical_tests(True, 'S'), {'community': 671, 'cerro-reference': 462})
        for mode in ('community', 'cerro-reference'):
            source, passed, metadata = fixture(mode, True, True, 'S')
            passed.update(critical_extension=True, critical_generation='S', package_files=513,
                expected_test_count=audit.critical_tests(True, 'S')[mode])
            proof = audit.audit(lambda db, query: json.dumps(metadata), mode, source, passed,
                operational_extensions=True, quality_extension=True, critical_extension=True, critical_generation='S')
            self.assertEqual(proof['critical_generation'], 'S')
            for changes in ({'critical_generation': 'R3'}, {'critical_generation': None},
                    {'expected_test_count': audit.CRITICAL_TESTS[mode]}, {'package_files': 508}):
                with self.subTest(mode=mode, changes=changes), self.assertRaises(ValueError):
                    audit.verify(proof, mode, source, dict(passed, **changes), operational_extensions=True,
                        quality_extension=True, critical_extension=True, critical_generation='S')
            with self.assertRaises(ValueError):
                audit.verify(proof, mode, source, passed, operational_extensions=True,
                    quality_extension=True, critical_extension=True)
            for module in audit.S_VERSIONS:
                altered = dict(source)
                manifest = __import__('ast').literal_eval(altered[module + '/__manifest__.py'].decode())
                manifest['version'] = '18.0.1.0.0'
                altered[module + '/__manifest__.py'] = repr(manifest).encode()
                with self.subTest(module=module), self.assertRaises(ValueError):
                    audit.verify(proof, mode, altered, passed, operational_extensions=True,
                        quality_extension=True, critical_extension=True, critical_generation='S')
        for flag, generation in ((False, 'S'), (True, 'R4'), (1, 'S')):
            with self.assertRaises(ValueError): audit.critical_tests(flag, generation)

    def test_t_generation_requires_corrected_group_source_and_keeps_s_immutable(self):
        self.assertEqual(audit.critical_tests(True, 'S'), audit.critical_tests(True, 'T'))
        self.assertNotEqual(audit.S_VERSIONS, audit.T_VERSIONS)
        for mode in ('community', 'cerro-reference'):
            source, passed, metadata = fixture(mode, True, True, 'T')
            passed.update(critical_extension=True, critical_generation='T', package_files=513,
                expected_test_count=audit.critical_tests(True, 'T')[mode],
                security_group_fk_boundary=security_boundary(passed['database'],mode))
            proof = audit.audit(lambda db, query: json.dumps(security_metadata(db,7002) if query==audit.SECURITY_GROUP_FK_QUERY else metadata), mode, source, passed,
                operational_extensions=True, quality_extension=True, critical_extension=True, critical_generation='T')
            self.assertEqual(proof['critical_generation'], 'T')
            self.assertTrue(proof['observed']['security_group_fk']['semantics_and_model_field_identities_preserved'])
            for altered in (dict(passed, critical_generation='S'), dict(passed, package_files=512)):
                with self.assertRaises(ValueError):
                    audit.verify(proof, mode, source, altered, operational_extensions=True,
                        quality_extension=True, critical_extension=True, critical_generation='T')
            old_source = fixture_source(True, True, 'S')
            with self.assertRaises(ValueError):
                audit.verify(proof, mode, old_source, passed, operational_extensions=True,
                    quality_extension=True, critical_extension=True, critical_generation='T')

    def test_t_security_fk_rejects_cascade_missing_validation_wrong_namespace_and_model_fields(self):
        database='MANAGEMENT_QA_CERRO_PAYROLL_API_SYNTHETIC'
        original=security_capture(database,'postflight')
        for change in ('cascade','noaction','unvalidated','deferred','deferrable','composite','target','column','name',
                'definition','field','model','nullable','duplicate','rw','cross_database','query'):
            altered=deepcopy(original);meta=altered['metadata'];fk=meta['foreign_keys'][0]
            if change=='cascade':fk['on_delete']='c'
            if change=='noaction':fk['on_delete']='a'
            if change=='unvalidated':fk['validated']=False
            if change=='deferred':fk['deferred']=True
            if change=='deferrable':fk['deferrable']=True
            if change=='composite':fk['source_columns']=['group_id','rule_group_id']
            if change=='target':fk['target_table']='res_users'
            if change=='column':fk['target_columns']=['other_id']
            if change=='name':fk['name']='another_name'
            if change=='definition':fk['definition']='FOREIGN KEY (group_id) REFERENCES res_groups(id) ON DELETE CASCADE'
            if change=='field':meta['fields'][0]['relation']='res.users'
            if change=='model':meta['models'][0]['model']='another.model'
            if change=='nullable':meta['column']['not_null']=False
            if change=='duplicate':meta['foreign_keys'].append(dict(fk,oid=8000))
            if change=='rw':meta['transaction_read_only']='off'
            if change=='cross_database':meta['database']='production'
            if change=='query':altered['query_sha256']='0'*64
            with self.subTest(change=change),self.assertRaises(ValueError):audit.verify_security_group_fk(altered,database,'postflight')

    def test_t_security_boundary_requires_preupgrade_capture_lease_and_no_manual_ddl_without_oid_identity_gate(self):
        database='MANAGEMENT_QA_CERRO_PAYROLL_API_SYNTHETIC'
        boundary=security_boundary(database,'cerro-reference')
        current=security_capture(database,'postflight',7002)
        result=audit.verify_security_group_fk_boundary(boundary,'cerro-reference',database,current)
        self.assertFalse(result['constraint_oid_unchanged'])
        self.assertFalse(result['constraint_oid_is_business_identity_gate'])
        self.assertTrue(result['native_before_upgrade_baseline'])
        for change in ('before','lease','manual_ddl','before_seal','after_seal','field_identity','drift'):
            altered=deepcopy(boundary);post=deepcopy(current)
            if change=='before':altered['before_native_upgrade']=None
            if change=='lease':altered['recorded_under_shared_environment_lease']=False
            if change=='manual_ddl':altered['manual_security_ddl_performed_by_validator']=True
            if change=='before_seal':altered['before_native_upgrade_sha256']='0'*64
            if change=='after_seal':altered['after_tests_sha256']='0'*64
            if change=='field_identity':post['metadata']['fields'][0]['id']=99
            if change=='drift':post['metadata']['foreign_keys'][0]['on_delete']='c'
            with self.subTest(change=change),self.assertRaises(ValueError):
                audit.verify_security_group_fk_boundary(altered,'cerro-reference',database,post)
        cold_database='COMMUNITY_PAYROLL_API_SYNTHETIC'
        cold=security_boundary(cold_database,'community')
        observed=audit.verify_security_group_fk_boundary(cold,'community',cold_database,security_capture(cold_database,'postflight',7002))
        self.assertIsNone(observed['baseline_constraint_oid']);self.assertFalse(observed['native_before_upgrade_baseline'])
        cold['before_native_upgrade']=security_capture(cold_database,'before-native-upgrade')
        with self.assertRaises(ValueError):audit.verify_security_group_fk_boundary(cold,'community',cold_database,security_capture(cold_database,'postflight',7002))

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
