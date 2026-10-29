"""Synthetic metadata/configuration only; no payroll model or rule execution."""
import copy
import hashlib
import json
import unittest
from unittest.mock import patch

import payroll_configuration_adoption_preflight as gate


PRIVATE_FORMULA = 'SYNTHETIC_FORMULA_DO_NOT_EXPOSE'
PRIVATE_LABEL = 'SYNTHETIC_LABEL_DO_NOT_EXPOSE'


def fixtures():
    data = {
        'hr_payroll_structure': [dict(id=10, name=PRIVATE_LABEL, journal_id={'1': 20, '2': 21}, report_id=462)],
        'hr_payroll_structure_type': [dict(id=11, name=PRIVATE_LABEL)],
        'hr_payslip_input_type': [dict(id=12, name=PRIVATE_LABEL)],
        'hr_salary_rule': [dict(id=13, name={'en_US': PRIVATE_LABEL}, struct_id=10, note=None,
                               amount_python_compute=PRIVATE_FORMULA)],
        'hr_salary_rule_category': [dict(id=14, name={'en_US': PRIVATE_LABEL})],
    }
    capsule = dict(schema=1, read_only=True, orm_loaded=False, rules_evaluated=False,
        historical_payroll_read=False, engine_converted=False, financial_certified=False,
        import_authorized_by_capsule=False, tables={}, xmlids=[], external_references={})
    source, target = {}, {}
    for table, model in gate.TABLES.items():
        raw = [json.dumps(row) for row in data[table]]
        digest = hashlib.sha256('\n'.join(raw).encode()).hexdigest()
        capsule['tables'][table] = dict(model=model, rows_json=raw, row_count=len(raw), rows_sha256=digest)
        capsule['xmlids'].append(dict(id=len(capsule['xmlids']) + 1, module='synthetic', name=table,
            model=model, res_id=data[table][0]['id'], noupdate=True))
        source['source_hash:' + table] = [dict(rows_sha256=digest)]
        target['rows:' + table] = []
    capsule['external_references'] = {
        'hr_payroll_structure.journal_id': dict(target='account_journal', company_dependent=True,
            ids=[20,21], company_ids=[1,2], target_adopted=False,
            original_values=[dict(id=10, company_id=1, value=20), dict(id=10, company_id=2, value=21)]),
        'hr_payroll_structure.report_id': dict(target='ir_act_report_xml', ids=[462], target_adopted=False),
    }
    fields = []
    for model, name, translate in (('hr.payslip.input.type','name',False),
            ('hr.salary.rule','note',True),('hr.payroll.structure','journal_id',False)):
        fields.append(dict(model=model,name=name,ttype='many2one' if name=='journal_id' else 'char',
            relation='account.journal' if name=='journal_id' else None, required=False,readonly=False,
            store=True,related=None,company_dependent=name=='journal_id',translate=translate,on_delete=None))
    for metadata, native in ((source,True),(target,False)):
        metadata.update(fields=copy.deepcopy(fields), xmlids=[], group_aliases=[], implied_groups=[],
                        acl=[], rules=[], rule_groups=[], field_groups=[])
        module='hr_payroll' if native else 'payroll'
        user, manager, internal = (1,2,3) if native else (101,102,103)
        metadata['group_aliases'] = [dict(module=module,name='group_hr_payroll_user' if native else 'group_payroll_user',res_id=user),
            dict(module=module,name='group_hr_payroll_manager' if native else 'group_payroll_manager',res_id=manager),
            dict(module='base',name='group_user',res_id=internal)]
        metadata['implied_groups'] = [dict(gid=manager,hid=user),dict(gid=user,hid=internal)]
        for model in gate.TABLES.values():
            metadata['acl'].extend([
                dict(model=model,active=True,group_id=user,perm_read=True,perm_write=native,perm_create=native,perm_unlink=native),
                dict(model=model,active=True,group_id=manager,perm_read=True,perm_write=True,perm_create=True,perm_unlink=True)])
    target['fields'][0]['translate']=True
    target['fields'][1]['translate']=False
    source_external = {
        'external:res_company': [dict(id=1,currency_id=1),dict(id=2,currency_id=1)],
        'external:account_journal': [dict(id=20,company_id=1),dict(id=21,company_id=2)],
        'external:ir_act_report_xml': [dict(id=462,model='hr.payslip',report_type='qweb-pdf')],
        'external_aliases:ir_act_report_xml': [dict(module='hr_payroll',name='action_report_payslip',model='ir.actions.report',res_id=462)],
    }
    target_external = {
        'external:res_company': [dict(id=1,currency_id=1)],
        'external:account_journal': [dict(id=20,company_id=1),dict(id=21,company_id=999)],
        'external_aliases:ir_act_report_xml': [dict(module='hr_payroll',name='action_report_payslip',model='ir.actions.act_window',res_id=462)],
        'report_actions': [dict(id=462,type='ir.actions.act_window')],
    }
    return capsule,source,target,source_external,target_external


class AdoptionPreflightCase(unittest.TestCase):
    def test_no_formula_or_label_is_exposed_even_in_private_assessment(self):
        inputs=fixtures(); report=gate.assess(*inputs)
        encoded=json.dumps(report)
        self.assertNotIn(PRIVATE_FORMULA,encoded)
        self.assertNotIn(PRIVATE_LABEL,encoded)
        self.assertFalse(report['salary_formulas_exposed'])
        self.assertFalse(report['rules_evaluated'])
        self.assertFalse(report['import_authorized'])
        self.assertFalse(report['adoption_ready'])

    def test_source_capsule_body_seal_cannot_drift(self):
        capsule,*_=fixtures()
        capsule['tables']['hr_salary_rule']['rows_json'][0]+=' '
        with self.assertRaisesRegex(gate.PreflightError,'capsule-row-digest'):
            gate.capsule_rows(capsule)
        capsule,*_=fixtures();capsule['xmlids'][0]['res_id']=999999
        with self.assertRaisesRegex(gate.PreflightError,'capsule-dangling-xmlid'):
            gate.capsule_rows(capsule)
        capsule,*_=fixtures();capsule['tables']['hr_salary_rule']['foreign_keys']=[dict(validated=False)]
        with self.assertRaisesRegex(gate.PreflightError,'unvalidated-original-relation'):
            gate.capsule_rows(capsule)

    def test_occupied_source_ids_are_never_overwrite_permission(self):
        inputs=fixtures(); inputs[2]['rows:hr_payroll_structure']=[dict(id=10,row_sha256='different')]
        report=gate.assess(*inputs)
        self.assertEqual(len(report['occupied_source_ids']),1)
        self.assertFalse(report['occupied_source_ids'][0]['strict_sql_row_equal'])
        self.assertFalse(report['occupied_source_ids'][0]['overwrite_authorized'])

    def test_xmlid_collision_with_a_different_model_is_detected(self):
        inputs=fixtures()
        row=dict(inputs[0]['xmlids'][0],model='ir.ui.view')
        inputs[2]['xmlids']=[row]
        report=gate.assess(*inputs)
        self.assertEqual(len(report['xmlid_conflicts']),1)
        self.assertEqual(report['xmlid_conflicts'][0]['target_model'],'ir.ui.view')
        query=gate.queries(inputs[0])['xmlids']
        self.assertIn('OR (module,name) IN',query)

    def test_json_property_keeps_all_keys_and_detects_wrong_company(self):
        report=gate.assess(*fixtures())
        item=report['company_properties'][0]
        self.assertEqual((item['mapping_rows'],item['value_slots']),(1,2))
        self.assertFalse(item['scalarization_permitted'])
        self.assertFalse(item['source_owner_issues'])
        self.assertEqual(len(item['target_owner_issues']),1)

    def test_scalarization_or_bad_reference_snapshot_fails_closed(self):
        inputs=fixtures()
        raw=json.loads(inputs[0]['tables']['hr_payroll_structure']['rows_json'][0]);raw['journal_id']=20
        value=json.dumps(raw);inputs[0]['tables']['hr_payroll_structure']['rows_json']=[value]
        inputs[0]['tables']['hr_payroll_structure']['rows_sha256']=hashlib.sha256(value.encode()).hexdigest()
        with self.assertRaisesRegex(gate.PreflightError,'company-property-must-remain-object-or-null'):
            gate.assess(*inputs)
        inputs=fixtures();inputs[0]['external_references']['hr_payroll_structure.journal_id']['original_values']=[]
        with self.assertRaisesRegex(gate.PreflightError,'company-property-capsule-reference-drift'):
            gate.assess(*inputs)

    def test_translation_shapes_are_reported_without_inventing_language(self):
        report=gate.assess(*fixtures())
        name,note=report['translations']
        self.assertEqual((name['scalar_rows'],name['object_rows']),(1,0))
        self.assertEqual(name['languages'],[])
        self.assertFalse(name['literal_base_language_policy_approved'])
        self.assertEqual(note['null_rows'],1)
        self.assertTrue(note['source_translate']);self.assertFalse(note['target_translate'])

    def test_physical_translation_column_difference_is_not_hidden(self):
        inputs=fixtures()
        inputs[1]['columns']=[dict(table_name='hr_payslip_input_type',column_name='name',data_type='character varying',is_nullable='NO')]
        inputs[2]['columns']=[dict(table_name='hr_payslip_input_type',column_name='name',data_type='jsonb',is_nullable='NO')]
        report=gate.assess(*inputs)
        self.assertEqual(report['column_differences'],[dict(table='hr_payslip_input_type',field='name',differences=['data_type'])])

    def test_source_fields_and_new_target_owners_require_explicit_policy(self):
        inputs=fixtures()
        original=inputs[1]['fields'][0]
        inputs[0]['field_metadata']=[dict(model=original['model'],name=original['name'],type='integer',
            relation=None,required=False,readonly=False,store=True,related=None,company_dependent=False)]
        inputs[2]['fields'].append(dict(model='hr.payroll.structure',name='company_id',
            ttype='many2one',relation='res.company',required=False,readonly=False,store=True,
            related=None,company_dependent=False,translate=False,on_delete='restrict'))
        report=gate.assess(*inputs)
        self.assertFalse(report['source_capsule_field_metadata_matches'])
        self.assertEqual(report['target_only_company_fields'],[
            dict(model='hr.payroll.structure',field='company_id',explicit_null_required_for_originals=True)])

    def test_roles_use_canonical_xmlids_and_implied_groups_not_cross_database_ids(self):
        report=gate.assess(*fixtures())
        self.assertEqual(len(report['role_acl_differences']),5)
        self.assertEqual({row['role'] for row in report['role_acl_differences']},{'user'})
        self.assertTrue(all(row['source']['write'] and not row['target']['write'] for row in report['role_acl_differences']))
        self.assertTrue(all(not row['grants_authorized'] for row in report['role_acl_differences']))

    def test_field_group_restriction_differences_are_detected(self):
        inputs=fixtures()
        inputs[2]['field_groups']=[dict(model='hr.salary.rule',name='note',group_id=102)]
        report=gate.assess(*inputs)
        item=next(row for row in report['field_group_differences'] if row['role']=='user')
        self.assertTrue(item['source_visible']);self.assertFalse(item['target_visible'])

    def test_report_462_occupied_by_non_report_is_blocked(self):
        report=gate.assess(*fixtures())
        self.assertEqual(report['report_action_type_conflicts'],[dict(id=462,type='ir.actions.act_window')])
        item=next(row for row in report['external_references'] if row['table']=='ir_act_report_xml')
        self.assertEqual(item['missing_target_ids'],[462])
        self.assertEqual(len(item['alias_collisions']),1)

    def test_company_presence_is_not_proof_of_identity(self):
        inputs=fixtures()
        inputs[3]['company_identity']=[dict(id=1,name_sha256='source',vat_sha256='source')]
        inputs[4]['company_identity']=[dict(id=1,name_sha256='target',vat_sha256='target')]
        before=copy.deepcopy(inputs[3:])
        report=gate.assess(*inputs)
        item=next(row for row in report['external_references'] if row['table']=='res_company')
        self.assertFalse(item['numeric_presence_proves_identity'])
        self.assertTrue(item['metadata_identity_differences'])
        self.assertEqual(inputs[3:],tuple(before))

    def test_production_is_rejected_before_subprocess(self):
        with patch.object(gate.subprocess,'run') as runner:
            for name in ('CERRO_EL_PLOMO','SyS','karo_consultorias','QA_CERROELPLOMO'):
                with self.assertRaisesRegex(gate.PreflightError,'private-database-required'):
                    gate.run_snapshot(name,{})
            runner.assert_not_called()

    def test_sql_never_contains_the_private_capsule_body(self):
        inputs=fixtures()
        statements=gate.queries(inputs[0])
        text='\n'.join(statements.values())
        self.assertNotIn(PRIVATE_FORMULA,text)
        self.assertNotIn(PRIVATE_LABEL,text)
        self.assertNotRegex(text.lower(),r'\b(?:insert|update|delete|alter|create|drop)\s')
        self.assertIn('sha256',text)

    def test_read_only_repeat_comparison_keeps_schema_and_provenance_strict(self):
        before={name:{} for name in ('source_metadata','target_metadata','source_external_metadata','target_external_metadata')}
        before.update(capsule_sha256='sealed',source_database='SOURCE',target_database='TARGET',tool_sha256='tool')
        after=copy.deepcopy(before)
        self.assertTrue(gate.compare_reports(before,after)['read_only_evidence_unchanged'])
        after['target_metadata']['acl']='changed'
        result=gate.compare_reports(before,after)
        self.assertFalse(result['read_only_evidence_unchanged'])
        self.assertEqual(result['changed_sections'],['target_metadata'])


if __name__=='__main__':
    unittest.main(verbosity=2)
