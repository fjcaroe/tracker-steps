"""Exercise the original employee payroll role with two synthetic owners on isolated SyS copies."""

import json
import re

from odoo import api, Command
from odoo.addons.base.models.ir_qweb import QWebException
from odoo.exceptions import AccessError
from odoo.tests.common import new_test_user
from psycopg2 import sql


def copied_row(env, table, source_id, replacements):
    if table not in ('hr_contract', 'hr_payslip', 'hr_payslip_line'):
        raise ValueError('Unsupported fixture table')
    env.cr.execute('SELECT nextval(pg_get_serial_sequence(%s,%s))', (table, 'id'))
    ident, = env.cr.fetchone()
    statement = sql.SQL('INSERT INTO {table} SELECT (jsonb_populate_record(NULL::{table},'
                        'to_jsonb(t) || %s::jsonb)).* FROM {table} t WHERE id=%s').format(table=sql.Identifier(table))
    env.cr.execute(statement, (json.dumps(dict(replacements, id=ident)), source_id))
    assert env.cr.rowcount == 1
    return ident


def allowed_call(fn):
    try:
        fn()
    except AccessError:
        return False
    except QWebException as failure:
        error = failure.__cause__ or failure.__context__
        while error:
            if isinstance(error, AccessError):
                return False
            error = error.__cause__ or error.__context__
        raise
    return True


def prepare_actors(env, company_id):
    if not re.fullmatch(r'COMMUNITY_SYS_REPORT_ROLES_[A-Z0-9]+', env.cr.dbname):
        raise ValueError('Only a dedicated pre-seal employee-role fixture can persist actors')
    admin = env(context=dict(env.context, allowed_company_ids=[company_id], tracking_disable=True, no_reset_password=True))
    logins = [f'synthetic_sys_report_{i}' for i in (1, 2)]
    if admin['res.users'].with_context(active_test=False).search_count([('login', 'in', logins)]):
        raise ValueError('Use a fresh role fixture')
    return [new_test_user(admin, login=login, groups='base.group_user,l10n_cl_simpledigital_payroll.group_hr_payroll_employee',
                          company_id=company_id, company_ids=[Command.set([company_id])]).id for login in logins]


def run(env, company_id, prepared=False):
    if not re.fullmatch(r'(?:COMMUNITY|MANAGEMENT_QA)_SYS_REPORT_ROLES_[A-Z0-9]+', env.cr.dbname):
        raise ValueError('Use a new isolated SyS report-role derivative')
    env.cr.execute("""SELECT p.id,p.contract_id FROM hr_payslip p WHERE p.company_id=%s AND p.date_from='2026-10-01'
                      AND p.date_to='2026-10-31' AND p.state IN ('done','paid') ORDER BY p.id""", (company_id,))
    originals = env.cr.fetchall()
    assert len(originals) == 5
    env.cr.execute("""SELECT u.id FROM res_users u JOIN res_company_users_rel cu ON cu.user_id=u.id
                      WHERE cu.cid=%s AND u.active AND NOT u.share AND u.id NOT IN (1,2) ORDER BY u.id""", (company_id,))
    real_actors = [uid for uid, in env.cr.fetchall()]
    assert real_actors
    company = env['res.company'].browse(company_id)
    ctx = dict(env.context, allowed_company_ids=[company.id], tracking_disable=True, no_reset_password=True)
    admin = env(context=ctx)
    def read(env_for, ids):
        return allowed_call(lambda: env_for['hr.payslip'].browse(ids).check_access('read'))
    real_readers = [read(api.Environment(env.cr, uid, ctx), [ident for ident, _ in originals]) for uid in real_actors]
    action = env.ref('hr_payroll.action_report_payslip')
    assert action.id == 1431
    fixtures = []
    with env.cr.savepoint() as trial:
        for number, (source_slip, source_contract) in enumerate(originals[:2], 1):
            login = f'synthetic_sys_report_{number}'
            if prepared:
                user = admin['res.users'].search([('login', '=', login), ('company_id', '=', company.id)])
                user.ensure_one()
                assert user.with_user(user).has_group('l10n_cl_simpledigital_payroll.group_hr_payroll_employee')
                assert not user.with_user(user).has_group('payroll.group_payroll_user')
            else:
                user = new_test_user(admin, login=login, groups='base.group_user,l10n_cl_simpledigital_payroll.group_hr_payroll_employee',
                    company_id=company.id, company_ids=[Command.set(company.ids)])
            employee = admin['hr.employee'].create({'name': f'Synthetic payroll owner {number}', 'company_id': company.id,
                                                     'user_id': user.id, 'resource_calendar_id': company.resource_calendar_id.id})
            contract = copied_row(admin, 'hr_contract', source_contract,
                                  {'employee_id': employee.id, 'name': f'Synthetic contract {number}', 'wage': 1200})
            reference = f'SYNTHETIC_SYS_ROLE_{number}'
            slip = copied_row(admin, 'hr_payslip', source_slip, {'name': reference, 'number': reference,
                'employee_id': employee.id, 'contract_id': contract, 'move_id': None, 'payslip_run_id': None,
                'net_wage': 1200, 'gross_wage': 1200, 'basic_wage': 1200})
            env.cr.execute("SELECT id FROM hr_payslip_line WHERE slip_id=%s AND code='NET'", (source_slip,))
            net_source, = env.cr.fetchall()
            net_line = copied_row(admin, 'hr_payslip_line', net_source[0], {'slip_id': slip, 'employee_id': employee.id,
                'contract_id': contract, 'amount': 1200, 'total': 1200, 'quantity': 1, 'rate': 100, 'ytd': 1200})
            fixtures.append((user.id, employee.id, slip, net_line))
        env.flush_all()
        results = []
        for idx, (uid, employee_id, own, own_line) in enumerate(fixtures):
            foreign, foreign_line = fixtures[1-idx][2:]
            scope = api.Environment(env.cr, uid, ctx)
            assert not scope.su and scope.user.employee_id.id == employee_id
            report = scope['ir.actions.report']
            def render(ident):
                slip = scope['hr.payslip'].browse(ident)
                req = action.with_env(scope).report_action(slip, config=False)
                content, kind = report._render_qweb_html(req['report_name'], [ident])
                assert kind == 'html' and len(content)>200
            cases = {'read_own':read(scope,[own]), 'read_peer':read(scope,[foreign]),
                     'read_own_line':allowed_call(lambda: scope['hr.payslip.line'].browse(own_line).check_access('read')),
                     'read_peer_line':allowed_call(lambda: scope['hr.payslip.line'].browse(foreign_line).check_access('read')),
                     'print_own':allowed_call(lambda: render(own)), 'print_peer':allowed_call(lambda: render(foreign))}
            results.append(cases)
        trial.rollback()
    for _,_,ident,_ in fixtures:
        env.cr.execute('SELECT count(*) FROM hr_payslip WHERE id=%s',(ident,))
        assert env.cr.fetchone()==(0,)
    env.cr.rollback()
    return {'existing_ordinary_users':len(real_actors),'existing_read_all_october':sum(real_readers),
            'synthetic_employee_results':results,'business_fixtures_rolled_back':True}
