"""Compare new drafts on the real Cerro and OCA engines using original masters."""
from datetime import date, datetime, time
from decimal import Decimal
import traceback
from uuid import uuid4

import pytz
from odoo import Command
from odoo.exceptions import UserError

from probe_original_structure_required import require_private_pair


# These identities belong to the sealed Cerro configuration. Structure 4 is
# the Chilean monthly structure; 2 is the original active generic counterpart.
CASES = (
    {'structure': 4, 'unpaid': 11, 'rules': 47, 'essentials': [25, 26, 32]},
    {'structure': 2, 'unpaid': 6, 'rules': 8, 'essentials': [9, 10, 16]},
)
INPUTS = ((1, 1234), (2, 4321))


def decimal(value):
    return str(Decimal(str(value)).normalize())


def run_case(env, spec, community, progress, marker):
    model = env['hr.payslip'].with_user(7).with_context(tracking_disable=True, lang='en_US')
    company = model.env.company
    employee = model.env['hr.employee'].search([
        ('company_id', '=', company.id), ('resource_calendar_id', '!=', False)], order='id', limit=1)
    structure = model.env['hr.payroll.structure'].browse(spec['structure']).exists()
    calendar = employee.resource_calendar_id
    assert employee and structure and structure.active and calendar.hours_per_day > 0
    if structure.country_id and company.country_id != structure.country_id:
        raise UserError('The original operator company does not match the selected structure.')
    attendance = model.env.ref('hr_work_entry.work_entry_type_attendance')
    absence = model.env['hr.work.entry.type'].browse(spec['unpaid']).exists()
    assert absence.is_leave and absence in structure.unpaid_work_entry_type_ids
    types = model.env['hr.payslip.input.type'].browse([ident for ident, _ in INPUTS]).exists()
    assert types.ids == [ident for ident, _ in INPUTS] and all(types.mapped('active'))
    structure.rule_ids.check_access('read')
    expected_rules = sorted(structure.rule_ids.ids)
    assert len(expected_rules) == spec['rules']
    assert [structure.rule_ids.filtered(lambda rule: rule.code == code).id
            for code in ('BASIC', 'GROSS', 'NET')] == spec['essentials']

    progress['phase'] = 'contract'
    start, stop = date(2026, 11, 1), date(2026, 11, 30)
    contracts = env['hr.contract'].with_context(tracking_disable=True).with_company(company)
    contract_vals = {'name': marker, 'employee_id': employee.id, 'company_id': company.id,
        'date_start': start, 'resource_calendar_id': calendar.id, 'structure_type_id': structure.type_id.id,
        'wage': 720000}
    if 'struct_id' in contracts._fields:
        contract_vals['struct_id'] = structure.id
    contract = contracts.create(contract_vals)
    company.check_access('read')
    progress['phase'] = 'work_entries'
    zone = pytz.timezone(calendar.tz)
    entries = env['hr.work.entry'].with_context(tracking_disable=True)
    for kind, day in ((attendance, 2), (absence, 3)):
        span = [zone.localize(datetime.combine(start.replace(day=day), time(hour)))
                .astimezone(pytz.UTC).replace(tzinfo=None) for hour in (9, 13)]
        entries.create({'name': marker, 'employee_id': employee.id, 'company_id': company.id,
            'contract_id': contract.id, 'work_entry_type_id': kind.id, 'date_start': span[0], 'date_stop': span[1]})

    progress['phase'] = 'draft'
    values = {'name': marker, 'number': marker, 'employee_id': employee.id, 'company_id': company.id,
        'contract_id': contract.id, 'struct_id': structure.id, 'date_from': start, 'date_to': stop}
    if community:
        values['input_line_ids'] = [Command.create({'input_type_id': ident, 'amount': amount,
            'contract_id': contract.id}) for ident, amount in INPUTS]
    slip = model.create(values)
    if not community:
        slip.input_line_ids = [Command.clear()] + [Command.create({'input_type_id': ident, 'amount': amount})
                                                   for ident, amount in INPUTS]
    assert tuple(sorted((row.input_type_id.id, int(row.amount)) for row in slip.input_line_ids)) == INPUTS

    progress['phase'] = 'worked_days'
    computed = slip._get_worked_day_lines()
    expected_hours = {attendance.id: Decimal(4), absence.id: Decimal(4)}
    hours = {row['work_entry_type_id']: Decimal(str(row['number_of_hours'])) for row in computed}
    assert len(computed) == len(expected_hours) and hours == expected_hours, 'Original work-entry hours drifted'
    if not community:
        computed = [{key: value for key, value in row.items() if key in slip.worked_days_line_ids._fields
                     and key not in ('code', 'contract_id')} for row in computed]
    slip.worked_days_line_ids = [Command.clear()] + [Command.create(row) for row in computed]
    progress['inputs'] = [[ident, amount] for ident, amount in INPUTS]
    progress['worked_days'] = sorted([row.work_entry_type_id.id, decimal(row.number_of_hours),
        decimal(row.number_of_days), bool(row.is_paid)] for row in slip.worked_days_line_ids)
    assert all(row[3] == (row[0] == attendance.id) for row in progress['worked_days'])
    progress['original_rule_ids'] = expected_rules

    progress['phase'] = 'compute_sheet'
    assert slip.state == 'draft'
    slip.compute_sheet()
    assert slip.state in ('draft', 'verify') and slip.number == marker
    assert tuple(sorted((row.input_type_id.id, int(row.amount)) for row in slip.input_line_ids)) == INPUTS
    slip.line_ids.flush_recordset(['salary_rule_id', 'amount', 'quantity', 'rate', 'total'])
    env.cr.execute("""SELECT salary_rule_id, amount, quantity, rate, total
                      FROM hr_payslip_line WHERE slip_id=%s ORDER BY salary_rule_id, id""", (slip.id,))
    rows = env.cr.fetchall()
    assert set(spec['essentials']) <= {ident for ident, *_ in rows} <= set(expected_rules)
    progress['lines'] = [[ident, *(decimal(value) for value in values)] for ident, *values in rows]
    progress['phase'] = 'complete'


def run(env, database):
    require_private_pair(env, database)
    community = '_HANDOVER_' in database
    results = []
    for spec in CASES:
        marker = 'STEP_DRAFT_' + uuid4().hex
        progress = {'structure': spec['structure'], 'phase': 'original_masters'}
        try:
            run_case(env, spec, community, progress, marker)
        except Exception as exc:
            # The shell transcript is a private diagnostic. It may contain an
            # original rule expression and must never be copied to public logs.
            traceback.print_exc()
            progress['error_type'] = type(exc).__name__
        finally:
            env.cr.rollback()
        for model in ('hr.payslip', 'hr.contract', 'hr.work.entry'):
            assert not env[model].search_count([('name', '=', marker)])
        progress['fixture_rolled_back'] = True
        results.append(progress)
    return {'database': database, 'operator_uid': 7, 'community': community,
            'drafts_only': True, 'cases': results}
