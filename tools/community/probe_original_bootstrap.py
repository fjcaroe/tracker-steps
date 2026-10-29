"""Exercise real cold-registry forms/defaults/ACL, then roll back test actors.

No original configuration is imported and no payslip/contract is created.
The separate TransactionCases exercise the real OCA calculation engine.
"""
import hashlib
import json
import os
from pathlib import Path
import re


def counts(env):
    tables = ('hr_payroll_structure', 'hr_salary_rule', 'hr_salary_rule_category',
              'hr_payslip_input_type', 'hr_payslip', 'hr_payslip_input',
              'hr_payslip_line', 'hr_payslip_worked_days', 'hr_contract')
    result = {}
    for table in tables:
        env.cr.execute('SELECT count(*) FROM ' + table)
        result[table] = env.cr.fetchone()[0]
    return result


def exercise(env, output):
    from odoo import api, Command
    from odoo.exceptions import AccessError
    from odoo.tools import json_default
    from lxml import etree

    assert re.fullmatch('COMMUNITY_PAYROLL_API_ORIGINAL_BOOTSTRAP_[A-Za-z0-9_]+', env.cr.dbname)
    output = Path(output)
    assert output.is_absolute() and output.is_relative_to(Path('/opt/steps-validation'))
    before = counts(env)
    assert not any(before.values()), 'A cold registry must not contain salary masters or payroll history'
    env.cr.execute("SELECT name FROM ir_module_module WHERE name IN ('payroll','hr_payroll') AND state='installed'")
    assert {row[0] for row in env.cr.fetchall()} == {'payroll'}
    assert any(cls.__module__.startswith('odoo.addons.payroll.') for cls in type(env['hr.payslip']).__mro__)
    for alias in ('structure_chile', 'structure_type_chile'):
        assert not env.ref('l10n_cl_simpledigital_payroll.' + alias, raise_if_not_found=False)
    assert not env.ref('payroll.structure_base', raise_if_not_found=False)
    types = env['hr.payroll.structure.type'].with_context(active_test=False).search([])
    assert len(types) == 4, 'Only the four official hr_contract types are admitted'
    env.cr.execute("SELECT attname,format_type(atttypid,atttypmod),attnotnull,atthasdef "
        "FROM pg_attribute WHERE attrelid='hr_payslip_input'::regclass AND attnum>0 AND NOT attisdropped "
        "AND attname IN ('amount','code','contract_id') ORDER BY attname")
    input_columns = env.cr.fetchall()
    assert input_columns == [('amount', 'double precision', False, False),
        ('code', 'character varying', True, False), ('contract_id', 'integer', True, False)]
    company = env.company

    def actor(login, groups):
        user = env['res.users'].with_context(no_reset_password=True, tracking_disable=True).create({
            'name': 'Private cold registry actor', 'login': login, 'company_id': company.id,
            'company_ids': [Command.set(company.ids)],
            'groups_id': [Command.set([env.ref(name).id for name in groups])]})
        return api.Environment(env.cr, user.id, dict(env.context, allowed_company_ids=company.ids, lang='en_US'), su=False)

    scope = actor('private-cold-registry-manager', ('base.group_user', 'payroll.group_payroll_manager',
        'hr.group_hr_manager', 'account.group_account_manager'))
    assert not scope.su
    forms = {}
    for model, alias in (('hr.payslip', 'payroll.hr_payslip_view_form'),
                         ('hr.payslip.run', 'payroll.hr_payslip_run_view_form'),
                         ('hr.contract', 'hr_contract.hr_contract_view_form')):
        value = scope[model].get_view(view_id=scope.ref(alias).id, view_type='form')
        arch = value['arch']
        assert etree.fromstring(arch.encode()).tag == 'form'
        forms[model] = {'view_id': value['id'], 'arch_sha256': hashlib.sha256(arch.encode()).hexdigest()}
        json.dumps(value, default=json_default)
    run_arch = scope['hr.payslip.run'].get_view(view_id=scope.ref('payroll.hr_payslip_run_view_form').id, view_type='form')['arch']
    assert 'action_step_compute_existing_drafts' in run_arch
    visible = scope['ir.ui.menu']._visible_menu_ids(debug=False)
    assert scope.ref('payroll.payroll_menu_root').id in visible
    actions = scope['ir.actions.act_window'].search([('res_model', '=', 'hr.payslip')])
    assert actions and any('form' in action.view_mode for action in actions)
    defaults = {
        'hr.contract': scope['hr.contract'].default_get(['structure_type_id', 'struct_id', 'schedule_pay', 'wage_type']),
        'hr.payslip': scope['hr.payslip'].default_get(['struct_id', 'contract_id']),
    }
    assert all(not value.get('struct_id') for value in defaults.values()), 'No substitute salary structure may be selected'
    unpaid = scope.ref('l10n_cl_simpledigital_payroll.work_entry_type_unpaid_cl')
    assert not unpaid.unpaid_structure_ids, 'The original unpaid membership remains explicitly deferred'

    officer = actor('private-cold-registry-officer', ('base.group_user', 'payroll.group_payroll_user'))
    denied = False
    try:
        officer['hr.payslip.run'].check_access('read')
    except AccessError:
        denied = True
    assert denied, 'Cold bootstrap must not grant the officer access to payroll batches'
    internal = actor('private-cold-registry-internal', ('base.group_user',))
    assert not internal['hr.salary.rule'].has_access('write')
    assert not internal['hr.salary.rule'].has_access('create')
    result = {'database': env.cr.dbname, 'real_oca_engine': True, 'normal_actor': True,
        'forms': forms, 'defaults': defaults, 'visible_payroll_root': True,
        'payslip_actions': len(actions), 'officer_batch_read_denied': True,
        'internal_salary_rule_write_denied': True, 'official_structure_types': len(types),
        'salary_counts_before': before, 'input_columns': input_columns, 'deferred_unpaid_membership_adopted': False,
        'original_masters_imported': False, 'operational_package': False,
        'historical_conversion': False, 'financial_certified': False,
        'form_probe_created_payslips': False, 'form_probe_created_contracts': False}
    env.cr.rollback()
    assert counts(env) == before
    env.cr.execute("SELECT count(*) FROM res_users WHERE login LIKE 'private-cold-registry-%'")
    assert env.cr.fetchone()[0] == 0, 'Test actors leaked'
    result.update(actors_rolled_back=True, salary_counts_after=before,
        probe_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    with os.fdopen(os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w', encoding='utf-8') as stream:
        json.dump(result, stream, indent=2, default=json_default)
    return result
