"""Admit the missing stock Steps employee rules on a sealed private SyS role fixture."""

from hashlib import sha256
from io import BytesIO
import re

from lxml import etree
from odoo.tools import file_open
from odoo.tools.convert import convert_xml_import


MODULE = 'step_simpledigital_oca_security'
SOURCE = '9ba0d55473ba0c108c11c07e90396f72deab72e463ea588b5721527517d2a0b1'
MODELS = ('hr_payslip', 'hr_payslip_line', 'hr_payslip_input', 'hr_payslip_worked_days')
SCOPES = ('company', 'employee', 'officer', 'manager')


def original_policy(env):
    snapshots = {}
    queries = {
        'rules': 'SELECT to_jsonb(r) v FROM ir_rule r WHERE id <= 540 ORDER BY id',
        'groups': 'SELECT to_jsonb(g) v FROM res_groups g WHERE id <= 164 ORDER BY id',
        'rule_groups': 'SELECT to_jsonb(r) v FROM rule_group_rel r WHERE rule_group_id <= 540 ORDER BY rule_group_id,group_id',
        'user_groups': 'SELECT to_jsonb(g) v FROM res_groups_users_rel g ORDER BY gid,uid',
        'model_access': 'SELECT to_jsonb(a) v FROM ir_model_access a ORDER BY id',
    }
    for name, source in queries.items():
        env.cr.execute("SELECT count(*), md5(string_agg(v::text, '|')) FROM (" + source + ") source")
        snapshots[name] = env.cr.fetchone()
    return snapshots


def check_rule(env, xml, rule):
    name = xml.get('id')
    by_name = {field.get('name'): field for field in xml}
    model = env.ref(by_name['model_id'].get('ref'))
    groups = env['res.groups']
    if 'groups' in by_name:
        match = re.fullmatch(r"\[\(4,ref\('([\w.]+)'\)\)\]", by_name['groups'].get('eval'))
        if not match:
            raise ValueError('Unrecognized reviewed rule group')
        groups = env.ref(match[1])
    if (rule._name != 'ir.rule' or rule.model_id != model or rule.groups != groups or not rule.active
            or rule.domain_force.strip() != by_name['domain_force'].text.strip()
            or not all(rule[f'perm_{permission}'] for permission in ('read','write','create','unlink'))):
        raise ValueError('Existing employee scope differs from the approved rule: ' + name)


def run(env, apply=False):
    fixture = bool(re.fullmatch(r'COMMUNITY_SYS_REPORT_ROLES_[A-Z0-9]+', env.cr.dbname))
    if not fixture and (apply or env.cr.dbname != 'COMMUNITY_SYS_PREVIRED_COHORT_20261126U40I'):
        raise ValueError('Use a private SyS role fixture for admission or the integral cohort for verification')
    filename = MODULE + '/security.xml'
    with file_open(filename, 'rb') as stream:
        body = stream.read().replace(b'\r\n', b'\n')
    if sha256(body).hexdigest() != SOURCE:
        raise ValueError('Expected the reviewed published Steps rule file')
    rules = list(etree.fromstring(body).xpath('./data/record'))
    if {r.get('id') for r in rules} != {f'{model}_{scope}' for model in MODELS for scope in SCOPES}:
        raise ValueError('Expected the complete original Steps rule matrix')
    before = original_policy(env)
    missing = []
    for rule in rules:
        existing = env.ref(MODULE + '.' + rule.get('id'), raise_if_not_found=False)
        if existing:
            check_rule(env, rule, existing)
        else:
            missing.append(rule)
    if missing and not apply:
        raise ValueError('The Steps employee rules were not installed in this profile')
    with env.cr.savepoint():
        if missing:
            tree = etree.Element('odoo')
            section = etree.SubElement(tree, 'data', noupdate='1')
            for rule in missing:
                section.append(rule)
            extracted = BytesIO(etree.tostring(tree))
            extracted.name = filename
            convert_xml_import(env, MODULE, extracted, mode='init')
            env.flush_all()
        for rule in rules:
            check_rule(env, rule, env.ref(MODULE + '.' + rule.get('id')))
        if original_policy(env) != before:
            raise ValueError('The original SyS roles, memberships, rules or model access changed')
    return {'approved_rules':len(rules), 'added':len(missing), 'original_policy_preserved':True}
