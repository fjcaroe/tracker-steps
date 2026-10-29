"""Plan retained payroll security identities; never grant a right or import data.

The original salary-rule user already has CRUD. A real conversion must retain
that ACL and group, rather than add rights to an unrelated generic OCA user.
Only hashes/metadata leave PostgreSQL; salary formulas and user rows do not.
"""
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import stat

import payroll_configuration_adoption_preflight as gate


MODEL = 'hr.salary.rule'
GROUPS = ('hr_payroll.group_hr_payroll_user', 'hr_payroll.group_hr_payroll_manager',
          'payroll.group_payroll_user', 'payroll.group_payroll_manager', 'base.group_user')
SOURCE_COUNTRY_POLICY = "['|', ('struct_id.country_id', '=', False), ('struct_id.country_id', 'in', user.env.companies.mapped('country_id').ids)]"


def tree(domain):
    """Compare expression syntax without evaluating a domain or its calls."""
    return ast.dump(ast.parse(domain.strip(), mode='eval'), include_attributes=False)


def security_queries(capsule):
    result = gate.queries(capsule, source=True)
    selected = '(' + ','.join('(' + gate.literal(value.split('.')[0]) + ','
        + gate.literal(value.split('.')[1]) + ')' for value in GROUPS) + ')'
    model_ids = "SELECT id FROM ir_model WHERE model='hr.salary.rule'"
    acl_ids = 'SELECT id FROM ir_model_access WHERE model_id IN (' + model_ids + ')'
    rule_ids = 'SELECT id FROM ir_rule WHERE model_id IN (' + model_ids + ')'
    groups = "SELECT res_id FROM ir_model_data WHERE model='res.groups' AND (module,name) IN " + selected
    result['security_xmlids'] = ('SELECT id,module,name,model,res_id,noupdate FROM ir_model_data WHERE '
        "(model='res.groups' AND res_id IN (" + groups + ')) OR '
        "(model='ir.model' AND res_id IN (" + model_ids + ')) OR '
        "(model='ir.model.access' AND res_id IN (" + acl_ids + ')) OR '
        "(model='ir.rule' AND res_id IN (" + rule_ids + ')) ORDER BY module,name')
    result['security_models'] = 'SELECT id,model,state FROM ir_model WHERE id IN (' + model_ids + ') ORDER BY id'
    result['security_acl'] = ('SELECT id,model_id,group_id,active,perm_read,perm_write,perm_create,perm_unlink '
        'FROM ir_model_access WHERE id IN (' + acl_ids + ') ORDER BY id')
    result['security_rules'] = ('SELECT id,model_id,active,global,domain_force,perm_read,perm_write,perm_create,perm_unlink '
        'FROM ir_rule WHERE id IN (' + rule_ids + ') ORDER BY id')
    result['security_groups'] = ("SELECT id,category_id,share,encode(sha256(convert_to((to_jsonb(g)->'name')::text,'UTF8')),'hex') AS name_sha256 "
        'FROM res_groups g WHERE id IN (' + groups + ') ORDER BY id')
    result['security_membership_hashes'] = ("SELECT g.id,count(r.uid) AS members,encode(sha256(convert_to(coalesce(string_agg(r.uid::text,',' ORDER BY r.uid),''),'UTF8')),'hex') AS members_sha256 "
        'FROM res_groups g LEFT JOIN res_groups_users_rel r ON r.gid=g.id WHERE g.id IN (' + groups + ') GROUP BY g.id ORDER BY g.id')
    return result


def preservation_plan(source, target):
    blockers = []
    details = []

    def reject(code, **metadata):
        blockers.append(code)
        if metadata:
            details.append(dict(code=code, **metadata))

    source_aliases = {row['module'] + '.' + row['name']: row for row in source['security_xmlids']}
    target_aliases = {row['module'] + '.' + row['name']: row for row in target['security_xmlids']}
    original_groups = {}
    for name in GROUPS:
        row = source_aliases.get(name)
        if row is None or row['model'] != 'res.groups':
            reject('source-role-identity-missing', xmlid=name)
            continue
        original_groups[name] = row['res_id']
        other = target_aliases.get(name)
        if other != row:
            reject('original-role-xmlid-pk-or-noupdate-not-retained', xmlid=name)
    for native, oca in (('hr_payroll.group_hr_payroll_user', 'payroll.group_payroll_user'),
                        ('hr_payroll.group_hr_payroll_manager', 'payroll.group_payroll_manager')):
        if original_groups.get(native) != original_groups.get(oca) or native not in original_groups:
            reject('source-oca-alias-does-not-target-original-role', xmlid=oca)
    for name in ('hr_payroll.model_hr_salary_rule',):
        original = source_aliases.get(name)
        if original is None or original['model'] != 'ir.model':
            reject('source-model-alias-missing', xmlid=name)
        elif target_aliases.get(name) != original:
            reject('original-model-xmlid-pk-or-noupdate-not-retained', xmlid=name)
    native_model = source_aliases.get('hr_payroll.model_hr_salary_rule')
    oca_model_name = 'payroll.model_hr_salary_rule'
    original_oca_model = source_aliases.get(oca_model_name)
    target_oca_model = target_aliases.get(oca_model_name)
    if original_oca_model is not None:
        if target_oca_model != original_oca_model:
            reject('original-model-xmlid-pk-or-noupdate-not-retained', xmlid=oca_model_name)
    elif (not native_model or not target_oca_model or target_oca_model['model'] != 'ir.model'
          or target_oca_model['res_id'] != native_model['res_id']
          or target_oca_model['noupdate'] != native_model['noupdate']):
        reject('new-oca-model-alias-does-not-target-original-model', xmlid=oca_model_name)
    # A model/group may have more than one namespace owner (for example the
    # original accounting extension). Preserve every alias, not just payroll's.
    for name, original in source_aliases.items():
        if original['model'] in ('ir.model', 'res.groups') and target_aliases.get(name) != original:
            reject('original-model-or-group-alias-not-retained', xmlid=name)
    if source.get('security_models') != target.get('security_models'):
        reject('original-model-primary-key-not-retained')

    for section in ('security_groups', 'security_membership_hashes'):
        current = {row['id']: row for row in target[section]}
        for row in source[section]:
            if current.get(row['id']) != row:
                reject('original-' + section.replace('security_', '').replace('_', '-') + '-not-retained', group_id=row['id'])
    for name in GROUPS:
        group_id = original_groups.get(name)
        if group_id is not None and gate.closure(group_id, source['implied_groups']) != gate.closure(group_id, target['implied_groups']):
            reject('original-role-implied-closure-not-retained', xmlid=name)

    for section, model in (('security_acl', 'ir.model.access'), ('security_rules', 'ir.rule')):
        current = {row['id']: row for row in target[section]}
        for row in source[section]:
            original = dict(row); other = current.get(row['id'])
            if section == 'security_rules' and other is not None:
                original['domain_force'] = tree(original['domain_force'])
                other = dict(other, domain_force=tree(other['domain_force']))
            if original != other:
                reject('original-' + section.replace('security_', '') + '-not-retained', record_id=row['id'])
            aliases = [value for value in source['security_xmlids'] if value['model'] == model and value['res_id'] == row['id']]
            if not aliases:
                reject('source-security-record-without-xmlid', record_id=row['id'], model=model)
            for alias in aliases:
                name = alias['module'] + '.' + alias['name']
                if target_aliases.get(name) != alias:
                    reject('original-security-xmlid-pk-or-noupdate-not-retained', xmlid=name)

    source_rule_ids = {row['id'] for row in source['security_rules']}
    target_rule_ids = {row['id'] for row in target['security_rules']}
    source_links = [row for row in source['rule_groups'] if row['rule_group_id'] in source_rule_ids]
    target_links = [row for row in target['rule_groups'] if row['rule_group_id'] in source_rule_ids]
    if source_links != target_links:
        reject('original-record-rule-groups-not-retained')
    for row in target['security_rules']:
        if row['id'] not in source_rule_ids and row['active'] and not row['global']:
            reject('additional-group-record-rule-needs-review', record_id=row['id'])
    if not any(row['active'] and row['global'] and all(row['perm_' + op] for op in gate.OPERATIONS)
               and tree(row['domain_force']) == tree(SOURCE_COUNTRY_POLICY) for row in source['security_rules']):
        reject('source-global-country-policy-not-proven')
    for role in ('hr_payroll.group_hr_payroll_user', 'hr_payroll.group_hr_payroll_manager', 'base.group_user'):
        before, after = gate.effective_acl(source, role, MODEL), gate.effective_acl(target, role, MODEL)
        if before != after or before is None:
            reject('effective-original-role-rights-not-preserved', xmlid=role)
    user_rights = gate.effective_acl(source, 'hr_payroll.group_hr_payroll_user', MODEL)
    if user_rights != dict.fromkeys(gate.OPERATIONS, True):
        reject('source-payroll-user-crud-not-proven')
    source_field_names = {row['name'] for row in source['fields'] if row['model'] == MODEL}
    target_field_names = {row['name'] for row in target['fields'] if row['model'] == MODEL}
    for name in sorted(source_field_names - target_field_names):
        reject('original-field-absent', field=name)
    field_groups = lambda metadata: sorted((row['name'], row['group_id']) for row in metadata['field_groups']
                                          if row['model'] == MODEL and row['name'] in source_field_names)
    if field_groups(source) != field_groups(target):
        reject('original-field-group-restrictions-not-retained')
    installed = {row['name']: row for row in target['modules']}
    if 'payroll' not in installed or any(row['license'] == 'OEEL-1' for row in target['modules']):
        reject('target-not-community-oca-conversion')
    source_installed = {row['name']: row for row in source['modules']}
    if 'hr_payroll' not in source_installed:
        reject('native-source-engine-not-proven')
    return {'metadata_preservation_admissible': not blockers, 'blockers': sorted(set(blockers)),
        'details': details, 'original_group_ids': original_groups,
        'source_security_sha256': gate.digest(source), 'target_security_sha256': gate.digest(target),
        'original_acl_count': len(source['security_acl']), 'original_record_rule_count': len(source_rule_ids),
        'additional_target_record_rule_count': len(target_rule_ids - source_rule_ids),
        'new_acl_grants': [], 'group_memberships_changed': False, 'manager_assigned': False,
        'new_oca_model_alias_required': original_oca_model is None,
        'field_groups_changed': False, 'database_writes': False, 'import_authorized': False,
        'dependency_change_authorized': False, 'functional_actor_acceptance_required': True,
        'record_rule_equivalence_certified': False, 'engine_converted': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capsule', type=Path, required=True)
    parser.add_argument('--expected-capsule-sha256', required=True)
    parser.add_argument('--source-database', required=True)
    parser.add_argument('--target-database', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    gate.require(stat.S_IMODE(args.capsule.stat().st_mode) == 0o600, 'capsule-must-be-private-0600')
    raw = args.capsule.read_bytes()
    gate.require(hashlib.sha256(raw).hexdigest() == args.expected_capsule_sha256, 'capsule-seal-mismatch')
    capsule = json.loads(raw); gate.capsule_rows(capsule)
    gate.require(args.source_database.startswith('MANAGEMENT_QA_CERRO_PAYROLL_API_'), 'native-private-source-required')
    gate.require(args.target_database.startswith('COMMUNITY_PAYROLL_API_'), 'community-private-target-required')
    output = args.output.resolve()
    gate.require(args.output.is_absolute() and Path(__file__).resolve().parents[2] not in output.parents,
                 'private-output-outside-checkout-required')
    statements = security_queries(capsule)
    source, target = (gate.run_snapshot(database, statements) for database in (args.source_database, args.target_database))
    same_rows = all(source['source_hash:' + table][0]['rows_sha256'] == data['rows_sha256']
                    for table, data in capsule['tables'].items())
    plan = preservation_plan(source, target)
    if not same_rows:
        plan['blockers'].append('source-configuration-drift-from-sealed-capsule')
        plan['metadata_preservation_admissible'] = False
    report = {'schema': 1, 'read_only': True, 'orm_loaded': False, 'rules_evaluated': False,
        'salary_formulas_exposed': False, 'source_database': args.source_database,
        'target_database': args.target_database, 'capsule_sha256': args.expected_capsule_sha256,
        'tool_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'source_configuration_matches_capsule': same_rows, 'source': source, 'target': target, 'plan': plan}
    fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as stream:
        json.dump(report, stream, indent=2)
    print(json.dumps({'evidence': str(output), 'blockers': plan['blockers'],
                      'source_configuration_matches_capsule': same_rows, 'database_writes': False}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
