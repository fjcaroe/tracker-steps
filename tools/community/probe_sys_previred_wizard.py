"""Exercise the installed Previred wizard on an isolated SyS copy.

Feed this script to the Odoo shell over a Unix socket with HTTP, cron and
outbound networking disabled. The receipt contains no TXT or employee data.
"""
from base64 import b64decode
from calendar import monthrange
from collections import Counter
from datetime import date
import hashlib
import json
import re
from types import SimpleNamespace

from odoo.exceptions import UserError
from odoo.http import Response, _request_stack

from odoo.addons.step_hr_previred.tools import previred


PRIVATE_DB = re.compile(r'(?:MANAGEMENT_QA_SYS_PREVIRED_|COMMUNITY_SYS_PREVIRED_)[A-Za-z0-9_]+')
OCTOBER = date(2026, 10, 1)
WIZARD_TABLES = {'step_previred_batch', 'step_previred_export_wizard'}
BUSINESS_TABLES = ('hr_payslip', 'hr_payslip_line', 'hr_contract',
                   'hr_payslip_worked_days', 'hr_payslip_input', 'hr_payslip_run',
                   'account_move', 'account_move_line',
                   'ir_sequence', 'ir_sequence_date_range')


def snapshots(env):
    result = {}
    env.flush_all()
    for table in (*BUSINESS_TABLES, *sorted(WIZARD_TABLES)):
        env.cr.execute("SELECT count(*), md5(string_agg(md5(to_jsonb(t)::text),"
                       " '' ORDER BY id)) FROM " + table + ' t')
        result[table] = env.cr.fetchone()
    return result


def authorized_wizard(env, users, company, is_manager):
    for user in users.filtered(lambda candidate: company in candidate.company_ids):
        wizard = env['step.previred.export.wizard'].with_user(user).with_context(
            allowed_company_ids=[company.id])
        if (wizard.env.user.has_group('step_hr_previred.group_previred_generate')
                and is_manager(wizard.env)):
            return wizard
    return None


def check_txt(wizard, dataset, period):
    assert wizard.state == 'done' and wizard.batch_id.result == 'ok'
    assert wizard.file_name.endswith('.txt')
    data = b64decode(wizard.file_data)
    rows = [line.split(';') for line in data.decode(previred.ENCODING).splitlines()]
    assert rows and len(rows) == dataset.row_count
    assert all(len(row) == previred.FIELD_COUNT for row in rows)
    assert all(row[8:10] == [period.strftime('%m%Y')] * 2 for row in rows)
    assert len(dataset.records) == dataset.eligible_payslip_count
    assert len({record.payslip_id for record in dataset.records}) == len(dataset.records)
    afp = previred.F_AFP_CONTRIBUTION - 1
    principals = [row for row in rows if previred.normalize_line_type(
        row[previred.F_LINE_TYPE - 1]) == previred.LINE_PRINCIPAL]
    assert Counter((row[0], row[1], int(row[afp])) for row in principals) == Counter(
        (record.principal[0], record.principal[1], int(record.principal[afp]))
        for record in dataset.records)
    for record in dataset.records:
        assert record.payslip_id
        wizard.env.cr.execute(
            'SELECT sum(total) FROM hr_payslip_line '
            "WHERE slip_id = %s AND code IN ('AFP', 'AFP_EMP')",
            (record.payslip_id,))
        stored_afp = wizard.env.cr.fetchone()[0]
        assert stored_afp is not None
        assert int(record.principal[afp]) == int(abs(stored_afp))
    return dict(fields=previred.FIELD_COUNT, rows=len(rows), annexes=dataset.annex_count,
                operator_uid=wizard.env.uid, file_sha256=hashlib.sha256(data).hexdigest(),
                with_positive_afp=sum(int(row[afp]) > 0 for row in principals),
                compared_stored_afp=True)


def probe_cohort(wizard_model, start, count):
    end = start.replace(day=monthrange(start.year, start.month)[1])
    # The ORM, route map and supplier endpoint are real. Only the request
    # context is supplied locally, with the existing manager's environment.
    req = SimpleNamespace(env=wizard_model.env, make_response=Response,
                          update_env=lambda **kw: None)
    _request_stack.push(req)
    try:
        wizard = wizard_model.create(dict(
            company_id=wizard_model.env.company.id, date_from=start, date_to=end,
            allow_without_department=True, scope='consolidated', output='txt'))
        dataset = wizard._build()
        errors = dict(Counter(issue.code for issue in dataset.errors))
        diagnostic = dict(
            period=start.isoformat(), closed_cohort=count, principal=len(dataset.records),
            eligible=dataset.eligible_payslip_count, dropped=dataset.dropped_count,
            spec=dataset.spec_version, errors=errors,
            warnings=dict(Counter(issue.code for issue in dataset.warnings)))
        wizard.action_validate()
        assert wizard.state == 'preview' and not wizard.file_data
        wizard.action_generate()
        if errors:
            assert wizard.state == 'preview' and not wizard.file_data
            return diagnostic, None
        return diagnostic, check_txt(wizard, dataset, start)
    finally:
        _request_stack.pop()


def run(env):
    assert PRIVATE_DB.fullmatch(env.cr.dbname)
    community = env.cr.dbname.startswith('COMMUNITY_SYS_PREVIRED_')
    installed = env['ir.module.module'].search([('state', '=', 'installed')])
    enterprise_count = sum(module.license == 'OEEL-1' for module in installed)
    if community:
        assert enterprise_count == 0 and 'payroll' in installed.mapped('name')
        from odoo.addons.step_payroll_contracts.access import has_payroll_role

        def is_manager(role_env):
            return has_payroll_role(role_env, 'manager')
    else:
        def is_manager(role_env):
            return role_env.user.has_group('hr_payroll.group_hr_payroll_manager')

    env['ir.http'].routing_map()
    before = snapshots(env)
    env.cr.execute("""
        SELECT p.company_id, date_trunc('month',p.date_from)::date, count(*)
        FROM hr_payslip p JOIN hr_contract c ON c.id=p.contract_id
                          JOIN hr_employee e ON e.id=p.employee_id
        WHERE p.state IN ('verify','done','paid')
        GROUP BY 1,2
        HAVING bool_and(c.afp_option IS NOT NULL
            AND nullif(c.health_institution::text,'') IS NOT NULL
            AND e.identification_id IS NOT NULL)
        ORDER BY count(*) DESC, 2 DESC, 1
    """)
    cohorts = env.cr.fetchall()
    modules = env['ir.module.module'].search([
        ('state', '=', 'installed'),
        ('name', 'in', ['step_hr_previred', 'step_hr_previred_simpledigital',
                        'l10n_cl_simpledigital_payroll'])])
    users = env['res.users'].search([('active', '=', True), ('share', '=', False), ('id', '!=', 1)])
    diagnostics = []
    generated = {}
    october_candidates = []
    try:
        for company_id, start, count in cohorts:
            if start != OCTOBER or count != 5:
                continue
            wizard = authorized_wizard(env, users, env['res.company'].browse(company_id), is_manager)
            if wizard is None:
                continue
            try:
                with env.cr.savepoint():
                    diagnostic, proof = probe_cohort(wizard, start, count)
            except UserError as err:
                diagnostic = dict(period=start.isoformat(), closed_cohort=count,
                                  error_type=type(err).__name__)
                proof = None
            diagnostics.append(diagnostic)
            if proof:
                receipt = {**diagnostic, **proof, 'company_id': company_id}
                if community:
                    if (diagnostic['spec'] == '98' and diagnostic['eligible'] == 5
                            and not diagnostic['dropped'] and proof['rows'] == 5
                            and not proof['annexes'] and proof['with_positive_afp'] == 5):
                        october_candidates.append(receipt)
                else:
                    generated.setdefault(diagnostic['spec'], receipt)
            if not community and '98' in generated:
                break
        after = snapshots(env)
        assert all(after[table] == before[table] for table in BUSINESS_TABLES)
    finally:
        env.cr.rollback()
    assert snapshots(env) == before
    if len(october_candidates) == 1:
        generated['98'] = october_candidates[0]
    return dict(versions={m.name: m.latest_version for m in modules}, cohorts=len(cohorts),
                attempted=len(diagnostics), diagnostics=diagnostics, generated=generated,
                october_candidates=len(october_candidates),
                community=community, enterprise_count=enterprise_count,
                preserved=True, rolled_back=True)


print('STEPS_SYS_PREVIRED_RECEIPT', json.dumps(run(env)), flush=True)

