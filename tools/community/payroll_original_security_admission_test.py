"""Pure security metadata; no Odoo models, grants, user rows or private rules."""
import copy
import json
import unittest
from unittest.mock import patch

import payroll_original_security_admission as contract


def fixtures():
    aliases = [('hr_payroll', 'group_hr_payroll_user', 'res.groups', 45),
               ('hr_payroll', 'group_hr_payroll_manager', 'res.groups', 46),
               ('payroll', 'group_payroll_user', 'res.groups', 45),
               ('payroll', 'group_payroll_manager', 'res.groups', 46),
               ('base', 'group_user', 'res.groups', 1),
               ('hr_payroll', 'model_hr_salary_rule', 'ir.model', 200),
               ('payroll', 'model_hr_salary_rule', 'ir.model', 200),
               ('hr_payroll', 'access_hr_salary_rule', 'ir.model.access', 650),
               ('hr_payroll', 'salary_rule_country', 'ir.rule', 202)]
    source = dict(security_xmlids=[dict(id=1000+i,module=module,name=name,model=model,res_id=res_id,noupdate=True)
                                   for i,(module,name,model,res_id) in enumerate(aliases)],
        security_models=[dict(id=200,model=contract.MODEL,state='base')],
        security_groups=[dict(id=value,name_sha256='synthetic-name-'+str(value),category_id=7,share=False)
                         for value in (1,45,46)],
        security_membership_hashes=[dict(id=value,members=2,members_sha256='synthetic-members-'+str(value))
                                   for value in (1,45,46)],
        implied_groups=[dict(gid=46,hid=45),dict(gid=45,hid=1)],
        security_acl=[dict(id=650,model_id=200,group_id=45,active=True,perm_read=True,
                           perm_write=True,perm_create=True,perm_unlink=True)],
        security_rules=[dict(id=202,model_id=200,active=True,**{'global':True},
                             domain_force=contract.SOURCE_COUNTRY_POLICY,perm_read=True,
                             perm_write=True,perm_create=True,perm_unlink=True)],
        modules=[dict(name='hr_payroll',license='OEEL-1')],
        fields=[dict(model=contract.MODEL,name='code')],field_groups=[],rule_groups=[])
    source['acl']=[dict(row,model=contract.MODEL)for row in source['security_acl']]
    source['group_aliases']=[dict(module=module,name=name,res_id=res_id)for module,name,model,res_id in aliases if model=='res.groups']
    target=copy.deepcopy(source);target['modules']=[dict(name='payroll',license='AGPL-3')]
    return source,target


class OriginalSecurityAdmissionCase(unittest.TestCase):
    def test_preserved_crud_requires_no_grant_and_still_requires_actor_acceptance(self):
        report=contract.preservation_plan(*fixtures())
        self.assertTrue(report['metadata_preservation_admissible'])
        self.assertEqual(report['new_acl_grants'],[])
        self.assertFalse(report['manager_assigned'])
        self.assertFalse(report['database_writes'])
        self.assertFalse(report['import_authorized'])
        self.assertFalse(report['dependency_change_authorized'])
        self.assertFalse(report['record_rule_equivalence_certified'])
        self.assertTrue(report['functional_actor_acceptance_required'])

    def test_generic_oca_does_not_acquire_native_user_crud(self):
        source,target=fixtures()
        target['security_xmlids']=[row for row in target['security_xmlids']if row['module']!='hr_payroll']
        target['group_aliases']=[row for row in target['group_aliases']if row['module']!='hr_payroll']
        target['security_acl'][0]['perm_write']=False
        target['acl'][0]['perm_write']=False
        report=contract.preservation_plan(source,target)
        self.assertFalse(report['metadata_preservation_admissible'])
        self.assertIn('original-role-xmlid-pk-or-noupdate-not-retained',report['blockers'])
        self.assertEqual(report['new_acl_grants'],[])

    def test_noupdate_or_xmlid_primary_key_changes_are_rejected(self):
        for field,value in (('noupdate',False),('id',99999),('res_id',99999)):
            source,target=fixtures();target['security_xmlids'][0][field]=value
            report=contract.preservation_plan(source,target)
            self.assertIn('original-role-xmlid-pk-or-noupdate-not-retained',report['blockers'])

    def test_oca_role_alias_must_be_original_group_not_a_new_group(self):
        source,target=fixtures()
        source['security_xmlids'][2]['res_id']=59
        report=contract.preservation_plan(source,target)
        self.assertIn('source-oca-alias-does-not-target-original-role',report['blockers'])

    def test_role_name_category_membership_and_implied_manager_cannot_change(self):
        for section,field,value in (('security_groups','name_sha256','renamed'),
                                    ('security_groups','category_id',99),
                                    ('security_membership_hashes','members_sha256','new-member')):
            source,target=fixtures();target[section][1][field]=value
            self.assertFalse(contract.preservation_plan(source,target)['metadata_preservation_admissible'])
        source,target=fixtures();target['implied_groups'].append(dict(gid=45,hid=46))
        report=contract.preservation_plan(source,target)
        self.assertIn('original-role-implied-closure-not-retained',report['blockers'])

    def test_original_acl_cannot_be_replaced_by_equal_permissions_on_new_row(self):
        source,target=fixtures();target['security_acl'][0]['id']=999
        report=contract.preservation_plan(source,target)
        self.assertIn('original-acl-not-retained',report['blockers'])

    def test_new_oca_model_alias_must_target_existing_original_model_without_claiming_old_pk(self):
        source,target=fixtures()
        source['security_xmlids']=[row for row in source['security_xmlids']if row['module']+'.'+row['name']!='payroll.model_hr_salary_rule']
        report=contract.preservation_plan(source,target)
        self.assertTrue(report['metadata_preservation_admissible'])
        self.assertTrue(report['new_oca_model_alias_required'])
        next(row for row in target['security_xmlids']if row['module']+'.'+row['name']=='payroll.model_hr_salary_rule')['res_id']=999
        self.assertIn('new-oca-model-alias-does-not-target-original-model',contract.preservation_plan(source,target)['blockers'])

    def test_original_acl_and_country_rule_xmlids_keep_noupdate(self):
        source,target=fixtures();target['security_xmlids'][-1]['noupdate']=False
        report=contract.preservation_plan(source,target)
        self.assertIn('original-security-xmlid-pk-or-noupdate-not-retained',report['blockers'])

    def test_country_policy_cannot_be_replaced_by_allow_all_or_group_rule(self):
        source,target=fixtures();target['security_rules'][0]['domain_force']='[(1,"=",1)]'
        self.assertIn('original-rules-not-retained',contract.preservation_plan(source,target)['blockers'])
        source,target=fixtures();target['security_rules'][0]['global']=False
        self.assertIn('original-rules-not-retained',contract.preservation_plan(source,target)['blockers'])

    def test_country_policy_compares_syntax_without_running_user_expression(self):
        source,target=fixtures();target['security_rules'][0]['domain_force']='\n '+contract.SOURCE_COUNTRY_POLICY+'\n '
        with patch.object(contract,'eval',create=True,side_effect=AssertionError('Must not evaluate')):
            self.assertTrue(contract.preservation_plan(source,target)['metadata_preservation_admissible'])

    def test_extra_company_intersection_stays_uncertified_and_group_rule_is_blocked(self):
        source,target=fixtures()
        target['security_rules'].append(dict(target['security_rules'][0],id=212,
            domain_force="['|',('company_id','=',False),('company_id','in',company_ids)]"))
        report=contract.preservation_plan(source,target)
        self.assertTrue(report['metadata_preservation_admissible'])
        self.assertFalse(report['record_rule_equivalence_certified'])
        target['security_rules'][-1]['global']=False
        self.assertIn('additional-group-record-rule-needs-review',contract.preservation_plan(source,target)['blockers'])

    def test_field_groups_and_missing_fields_are_not_silently_relaxed(self):
        source,target=fixtures();target['field_groups']=[dict(model=contract.MODEL,name='code',group_id=46)]
        self.assertIn('original-field-group-restrictions-not-retained',contract.preservation_plan(source,target)['blockers'])
        source,target=fixtures();target['fields']=[]
        self.assertIn('original-field-absent',contract.preservation_plan(source,target)['blockers'])

    def test_an_added_global_acl_cannot_give_internal_users_payroll_permissions(self):
        source,target=fixtures()
        target['acl'].append(dict(target['acl'][0],id=651,group_id=None))
        self.assertIn('effective-original-role-rights-not-preserved',contract.preservation_plan(source,target)['blockers'])

    def test_native_reference_is_not_misreported_as_community_conversion(self):
        source,target=fixtures();target['modules']=copy.deepcopy(source['modules'])
        report=contract.preservation_plan(source,target)
        self.assertIn('target-not-community-oca-conversion',report['blockers'])

    def test_security_snapshot_sql_returns_no_user_records_or_rule_formulas(self):
        capsule={'xmlids':[dict(module='test',name='test')],'relations':[]}
        queries=contract.security_queries(capsule)
        selected='\n'.join(queries.values())
        self.assertNotIn('res_users',queries['security_membership_hashes'])
        self.assertIn('members_sha256',queries['security_membership_hashes'])
        self.assertIn('noupdate',queries['security_xmlids'])
        self.assertNotRegex(selected.lower(),r'\b(?:insert|update|delete|alter|create|drop)\s')
        self.assertNotIn('amount_python_compute',selected)


if __name__=='__main__':
    unittest.main(verbosity=2)
