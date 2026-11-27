"""Admit the missing stock Steps employee rules on sealed private SyS cohorts."""

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
    is_reference = env.cr.dbname == 'COMMUNITY_SYS_PREVIRED_COHORT_20261126U40J' and not apply
    if not fixture and not is_reference and env.cr.dbname != 'COMMUNITY_SYS_PREVIRED_COHORT_20261126U40I':
        raise ValueError('Use an isolated employee fixture or the accepted private integrated SyS cohort')
    if (env.ref('hr_payroll.action_report_payslip').id != 1431
            or env.ref('hr_payroll.group_hr_payroll_manager') != env.ref('payroll.group_payroll_manager')
            or env.ref('hr_payroll.group_hr_payroll_user') != env.ref('payroll.group_payroll_user')):
        raise ValueError('Expected the same original SyS action and payroll role identities')
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

def verify_real_actors(env, company_id):
    """Verify real October access without assigning groups or linking original staff."""
    from odoo import api

    policy = run(env, apply=False)
    env.cr.execute("""SELECT p.id, e.user_id
                      FROM hr_payslip p JOIN hr_employee e ON e.id=p.employee_id
                      WHERE p.company_id=%s AND p.date_from='2026-10-01' AND p.date_to='2026-10-31'
                        AND p.state IN ('done','paid') ORDER BY p.id""", (company_id,))
    rows = env.cr.fetchall()
    assert len(rows) == 5
    linked = sum(user_id is not None for _, user_id in rows)
    env.cr.execute("""SELECT u.id FROM res_users u JOIN res_company_users_rel cu ON cu.user_id=u.id
                      WHERE cu.cid=%s AND u.active AND NOT u.share AND u.id <> 1
                        AND u.login NOT IN ('synthetic_sys_report_1','synthetic_sys_report_2') ORDER BY u.id""",
                   (company_id,))
    real = [uid for uid, in env.cr.fetchall()]
    assert len(real) >= 1
    administrative = []
    for uid in real:
        actor = api.Environment(env.cr, uid, {'allowed_company_ids': [company_id]})
        assert not actor.su
        if actor.user.has_group('hr_payroll.group_hr_payroll_manager'):
            docs = actor['hr.payslip'].browse([ident for ident, _ in rows])
            docs.check_access('read')
            env.cr.execute('SELECT id FROM hr_payslip_line WHERE slip_id=ANY(%s) ORDER BY id', (docs.ids,))
            ids = [ident for ident, in env.cr.fetchall()]
            actor['hr.payslip.line'].browse(ids).check_access('read')
            administrative.append(len(ids))
    assert administrative and len(set(administrative)) == 1
    return dict(policy, active_internal=len(real), payroll_managers_verified=len(administrative),
                closed_slips=len(rows), lines_per_manager=administrative[0], employee_links=linked)
