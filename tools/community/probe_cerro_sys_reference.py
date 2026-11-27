"""Replay non-identifying inputs from one closed SyS payroll through Cerro's own rules."""
from datetime import datetime, time, timedelta
import hashlib
import json
import re
from uuid import uuid4
import pytz

from odoo import Command
from odoo.exceptions import UserError


SYS = 'MANAGEMENT_QA_SYS_PREVIRED_20261126U40N'
CERRO_NATIVE = 'MANAGEMENT_QA_CERRO_HR_FIELDS_20261126U40V'
CERRO_CE = 'COMMUNITY_PAYROLL_API_CERRO_SCOPE_20261126U40J'
CERRO_REVIEW = 'COMMUNITY_PAYROLL_CERRO_REVIEW_20261126U42F'
STRUCTURE = 'l10n_cl_simpledigital_payroll.structure_chile'
CONTRACT_FIELDS = (
    'wage hourly_wage wage_type schedule_pay date_start date_end afc_enrolled afc_enrolled_trabajador '
    'afp_option colocation cotizacion_apvc_empleador cotizacion_apvc_trabajador cotizacion_apvi '
    'cotizacion_cuenta2 extra_hours family_invalid_loads_count family_loads_segment '
    'family_maternal_loads_count family_simple_loads_count fonasa_type has_apvc has_apvi has_cuenta2 '
    'has_empleo_joven has_extra_hours has_family_loads has_gratification health_institution '
    'income_tax_type institucion_apvi_apvc is_retired_elderly isapre_calc_type isapre_plan_monto '
    'isapre_uf_valor movility pay_format_apvi_apc pension_option viatico_fijo work_schedule_id'
).split()
INTERVAL_FIELDS = 'sequence dayofweek hour_from hour_to day_period week_type display_type date_from date_to'.split()
TAX_FIELDS = ['first_line_to'] + [
    band + '_line_' + key for band in ('second', 'third', 'fourth', 'fifth', 'sixth', 'seventh', 'eighth')
    for key in ('from', 'to', 'factor', 'tasa_rebaja') if (band, key) != ('eighth', 'to')]


def read_values(record, names):
    record.check_access('read')
    record.check_field_access_rights('read', names)
    return {name: record[name] for name in names}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def calendar_snapshot(calendar):
    intervals = [dict(read_values(row, INTERVAL_FIELDS), entry_code=row.work_entry_type_id.code)
                 for row in calendar.attendance_ids]
    return dict(read_values(calendar, ['tz', 'hours_per_day', 'two_weeks_calendar', 'flexible_hours']),
                intervals=intervals)


def capture_sys(env, case, *, include_tax=False):
    if not __debug__ or env.cr.dbname != SYS:
        raise ValueError('Use the sealed native SyS reference.')
    env.cr.execute('SET TRANSACTION READ ONLY')
    scope = env['hr.payslip'].with_user(2).with_context(allowed_company_ids=[case['company']])
    structure = scope.env.ref(STRUCTURE)
    env.cr.execute("""SELECT p.id FROM hr_payslip p JOIN hr_employee e ON e.id=p.employee_id
        WHERE p.id=%s AND p.company_id=%s AND p.state IN ('done','paid') AND p.struct_id=%s AND p.date_from='2026-10-01'
          AND p.net_wage>0 AND e.hr_commune IS NOT NULL
          AND NOT EXISTS(SELECT FROM hr_payslip_input i WHERE i.payslip_id=p.id)
          AND (SELECT count(*) FROM hr_payslip_worked_days d WHERE d.payslip_id=p.id)=1
        ORDER BY p.id LIMIT 1""", [case['source'], scope.env.company.id, structure.id])
    source = env.cr.fetchone()
    if not source:
        raise ValueError('No closed reference with one original attendance line.')
    slip = scope.browse(source[0])
    slip.check_access('read')
    assert not slip.env.su and slip.env.company == slip.company_id and slip.state in ('done', 'paid')
    assert slip.struct_id == slip.env.ref(STRUCTURE) and str(slip.date_from) == '2026-10-01'
    assert not slip.input_line_ids and len(slip.worked_days_line_ids) == 1 and slip.net_wage > 0
    contract, employee = slip.contract_id, slip.employee_id
    assert contract.employee_id == employee and employee.hr_commune and employee.country_id and contract.contract_type_id.code
    assert all(contract._fields[name].type in ('boolean', 'integer', 'float', 'monetary', 'date', 'selection', 'char')
               for name in CONTRACT_FIELDS)
    calendar = contract.resource_calendar_id
    assert calendar and not calendar.attendance_ids.mapped('resource_id')
    zone = pytz.timezone(calendar.tz)
    start = zone.localize(datetime.combine(slip.date_from, time.min))
    end = zone.localize(datetime.combine(slip.date_to + timedelta(days=1), time.min))
    lower = start.astimezone(pytz.UTC).replace(tzinfo=None)
    upper = end.astimezone(pytz.UTC).replace(tzinfo=None)
    entries = slip.env['hr.work.entry'].search([('employee_id', '=', employee.id), ('contract_id', '=', contract.id),
        ('date_start', '<', upper), ('date_stop', '>', lower), ('state', '!=', 'cancelled')], order='date_start,id')
    assert entries and set(entries.mapped('work_entry_type_id.code')) == {'WORK100'}
    reference = {'contract': read_values(contract, CONTRACT_FIELDS), 'type_code': contract.contract_type_id.code,
            'nationality': employee.country_id.code, 'commune': employee.hr_commune.codigo,
            'commune_name': employee.hr_commune.name, 'commune_region': employee.hr_commune.state_id.code,
            'commune_country': employee.hr_commune.country_id.code,
            'analytic_ref': (contract.analytic_account_id.get_external_id().get(contract.analytic_account_id.id)
                             if contract.analytic_account_id else False),
            'has_analytic': bool(contract.analytic_account_id), 'period': [str(slip.date_from), str(slip.date_to)],
            'calendar': calendar_snapshot(calendar),
            'entries': [dict(read_values(r, ['date_start', 'date_stop', 'state']), code=r.work_entry_type_id.code) for r in entries],
            'days': [dict(read_values(r, ['sequence', 'number_of_days', 'number_of_hours']),
                          code=r.work_entry_type_id.code) for r in slip.worked_days_line_ids],
            'saved_result': digest(sorted((r.code, r.amount, r.quantity, r.rate, r.total) for r in slip.line_ids))}
    if include_tax:
        tax = one(slip.env['impuesto_2da_categoria'], [('date', '=', slip.date_from)])
        assert tax.currency_id and 'company_id' not in tax._fields
        reference['monthly_tax'] = dict(date=str(tax.date), name=tax.name, currency=tax.currency_id.name,
                                        values=read_values(tax, TAX_FIELDS))
    return reference


def one(model, domain):
    rows = model.search(domain, limit=2)
    if len(rows) != 1:
        raise ValueError('Original target master is absent or ambiguous on ' + model._name)
    return rows


def replay_cerro(env, fixture, *, trial_analytic_id=None, trial_tax=False, test_review=False):
    if not __debug__ or env.cr.dbname not in (CERRO_NATIVE, CERRO_CE, CERRO_REVIEW):
        raise ValueError('Use the isolated native or Community Cerro payroll candidate.')
    model = env['hr.payslip'].with_user(7).with_context(tracking_disable=True, mail_notify_force_send=False)
    model = model.with_context(allowed_company_ids=[model.env.company.id])
    actor = model.env
    company = actor.company
    assert not actor.su and company.country_id.code == 'CL'
    tag = 'STEP_CERRO_SYS_' + uuid4().hex
    progress = {'database': env.cr.dbname, 'input_digest': digest(fixture)}
    try:
        with env.cr.savepoint() as trial:
            progress['phase'] = 'masters'
            structure = actor.ref(STRUCTURE)
            assert len(structure.rule_ids.filtered('active')) == 47
            country = one(actor['res.country'], [('code', '=', fixture['nationality'])])
            commune = one(actor['res.country.commune'], [('codigo', '=', fixture['commune']),
                ('country_id.code', '=', fixture['commune_country']), ('state_id.code', '=', fixture['commune_region'])])
            assert commune.name.strip().casefold() == fixture['commune_name'].strip().casefold()
            contract_type = one(actor['hr.contract.type'], [('code', '=', fixture['type_code']),
                                  ('country_id', 'in', [False, company.country_id.id])])
            if trial_tax:
                progress['phase'] = 'monthly_tax_reference'
                table = actor['impuesto_2da_categoria']
                tax = fixture['monthly_tax']
                assert 'company_id' not in table._fields and tax['date'] == fixture['period'][0]
                assert set(tax['values']) == set(TAX_FIELDS)
                assert not table.with_context(active_test=False).search_count([('date', '=', tax['date'])])
                currency = one(actor['res.currency'], [('name', '=', tax['currency'])])
                row = table.create(dict(tax['values'], date=tax['date'], name=tax['name'], currency_id=currency.id))
                assert row.name == tax['name'] and str(row.date) == tax['date'] and row.currency_id == currency
                assert read_values(row, TAX_FIELDS) == tax['values']
                progress['monthly_tax_reference_matches'] = True
            def entry_type(code):
                return one(actor['hr.work.entry.type'], [('code', '=', code)])
            progress['phase'] = 'calendar'
            values = dict(fixture['calendar'])
            intervals = values.pop('intervals')
            calendar = company.resource_calendar_id
            if (not calendar or calendar.attendance_ids.mapped('resource_id')
                    or digest(calendar_snapshot(calendar)) != digest(fixture['calendar'])):
                calendar = actor['resource.calendar'].create(dict(values, name=tag, company_id=company.id,
                    attendance_ids=[Command.clear(), *[Command.create(dict(
                        {k: r[k] for k in INTERVAL_FIELDS}, name=tag,
                        work_entry_type_id=entry_type(r['entry_code']).id if r['entry_code'] else False)) for r in intervals]]))
            progress['calendar_matches_reference'] = digest(calendar_snapshot(calendar)) == digest(fixture['calendar'])
            assert progress['calendar_matches_reference']
            progress['phase'] = 'employee'
            person = actor['hr.employee'].create({'name': tag, 'company_id': company.id, 'country_id': country.id,
                'hr_commune': commune.id, 'resource_calendar_id': calendar.id})
            vals = dict(fixture['contract'], name=tag, company_id=company.id, employee_id=person.id,
                        contract_type_id=contract_type.id, structure_type_id=structure.type_id.id,
                        resource_calendar_id=calendar.id)
            if 'struct_id' in actor['hr.contract']._fields:
                vals['struct_id'] = structure.id
            if fixture.get('analytic_ref'):
                account = actor.ref(fixture['analytic_ref'], raise_if_not_found=False)
                if account and account._name == 'account.analytic.account' and account.company_id in (company, actor['res.company']):
                    account.check_access('read')
                    vals['analytic_account_id'] = account.id
            progress['source_analytic_link_matched'] = bool(vals.get('analytic_account_id'))
            if trial_analytic_id is not None:
                if vals.get('analytic_account_id'):
                    raise ValueError('Use the matching source account directly.')
                account = one(actor['account.analytic.account'], [
                    ('id', '=', trial_analytic_id), ('company_id', 'in', [False, company.id])])
                vals['analytic_account_id'] = account.id
                progress['trial_target_analytic_id'] = account.id
            progress['phase'] = 'contract'
            contract = actor['hr.contract'].create(vals)
            progress['contract_values_match_reference'] = digest(read_values(contract, CONTRACT_FIELDS)) == digest(fixture['contract'])
            assert progress['contract_values_match_reference']
            assert person.hr_commune == commune and person.country_id == country
            assert contract.contract_type_id == contract_type and contract.resource_calendar_id == calendar
            progress['contract_review'] = (bool(contract.step_payroll_migration_review)
                                           if 'step_payroll_migration_review' in contract._fields else None)
            required = ('health_institution', 'pension_option', 'income_tax_type',
                        'work_schedule_id', 'analytic_account_id', 'contract_type_id')
            progress['missing_contract_fields'] = [name for name in required if not contract[name]]
            if test_review:
                progress['phase'] = 'review_form'
                assert 'step_payroll_migration_review' in contract._fields
                form = contract.get_view(view_type='form')['arch']
                assert 'action_confirm_payroll_migration' in form
                with env.cr.savepoint() as action_trial:
                    contract.write({'step_payroll_migration_review': True})
                    assert contract.step_payroll_migration_review
                    try:
                        contract.write({'step_payroll_migration_review': False})
                    except UserError:
                        progress['direct_clear_rejected'] = True
                    else:
                        raise AssertionError('Contract review was cleared without the original action.')
                    try:
                        contract.action_confirm_payroll_migration()
                    except UserError:
                        progress['review_confirmation'] = 'refused'
                        assert contract.step_payroll_migration_review
                    else:
                        progress['review_confirmation'] = 'accepted'
                        assert not contract.step_payroll_migration_review
                    progress['pending_review_exercised'] = True
                    action_trial.rollback()
            progress['phase'] = 'entries'
            entries = actor['hr.work.entry'].create([{'name': tag, 'employee_id': person.id,
                'contract_id': contract.id, 'company_id': company.id, 'date_start': r['date_start'],
                'date_stop': r['date_stop'], 'work_entry_type_id': entry_type(r['code']).id, 'state': r['state']}
                for r in fixture['entries']])
            assert len(entries) == len(fixture['entries']) > 0
            observed_entries = [dict(read_values(row, ['date_start', 'date_stop', 'state']),
                                     code=row.work_entry_type_id.code)
                                for row in entries.sorted(lambda row: (row.date_start, row.id))]
            progress['work_entries_match_reference'] = digest(observed_entries) == digest(fixture['entries'])
            assert progress['work_entries_match_reference']
            progress['phase'] = 'draft'
            slip = model.create({'name': tag, 'number': tag, 'employee_id': person.id, 'contract_id': contract.id,
                'struct_id': structure.id, 'company_id': company.id, 'date_from': fixture['period'][0],
                'date_to': fixture['period'][1]})
            days = []
            for row in fixture['days']:
                kind = entry_type(row['code'])
                vals = dict(name=kind.name, work_entry_type_id=kind.id, sequence=row['sequence'],
                            number_of_days=row['number_of_days'], number_of_hours=row['number_of_hours'])
                if 'contract_id' in slip.worked_days_line_ids._fields and not slip.worked_days_line_ids._fields['contract_id'].related:
                    vals.update(code=row['code'], contract_id=contract.id)
                days.append(Command.create(vals))
            slip.worked_days_line_ids = [Command.clear(), *days]
            observed_days = [dict(read_values(row, ['sequence', 'number_of_days', 'number_of_hours']),
                                  code=row.work_entry_type_id.code) for row in slip.worked_days_line_ids]
            progress['worked_days_match_reference'] = digest(observed_days) == digest(fixture['days'])
            assert progress['worked_days_match_reference']
            progress['phase'] = 'compute'
            progress['stored_work_entries'] = len(entries)
            progress['stored_day_lines'] = len(slip.worked_days_line_ids)
            slip.compute_sheet()
            actor.flush_all()
            lines = sorted((r.code, r.amount, r.quantity, r.rate, r.total) for r in slip.line_ids)
            assert lines and any(r[0] == 'NET' for r in lines)
            progress.update(phase='calculated', stored_work_entries=len(entries), lines=len(lines), result=digest(lines),
                            matches_saved_sys=digest(lines) == fixture['saved_result'])
            progress['essential_lines'] = {code: {
                'count': sum(row[0] == code for row in lines),
                'positive_total': sum(row[-1] for row in lines if row[0] == code) > 0,
                'zero_total': sum(row[-1] for row in lines if row[0] == code) == 0}
                for code in ('BASIC', 'GROSS', 'NET')}
            trial.rollback()
    except Exception as exc:
        import traceback
        trace = traceback.extract_tb(exc.__traceback__)
        origin = trace[-1]
        progress.update(error=type(exc).__name__, method=origin.name, trace=[f.name for f in trace[-5:]],
                        origin='/'.join(origin.filename.replace('\\', '/').split('/')[-3:]), line=origin.lineno)
        if isinstance(exc, ValueError) and str(exc).startswith('Original target master is absent or ambiguous'):
            progress['master'] = str(exc).split()[-1]
        diagnostics = getattr(exc, 'diag', None)
        if diagnostics:
            progress['sql_table'] = diagnostics.table_name
            progress['sql_column'] = diagnostics.column_name
        message = str(exc).casefold()
        progress['configuration_codes'] = re.findall(r'\b[A-Z]{2,}_[A-Z_]{4,}\b', str(exc))
        progress['topics'] = [term for term in ('analytic', 'analítica', 'diario', 'journal', 'contract type',
            'comuna', 'calendario', 'calendar', 'attendance', 'asistencia', 'review', 'revisión', 'rut',
            'access', 'acceso', 'company', 'compañía', 'wage', 'sueldo', 'regla', 'rule', 'indicador',
            'gratificación', 'afp', 'isapre', 'previsional', 'institución', 'parámetro', 'fecha', 'periodo',
            'período', 'administrador', 'centro de costo', 'contrato', 'identificación', 'remuneración',
            'mandatory', 'required', 'employee', 'empleado', 'liquidación', 'plan', 'jornada') if term in message]
    finally:
        env.cr.rollback()
        env.invalidate_all(flush=False)
    return progress


def compare_target_accounts(env, fixture, *, trial_tax=False):
    """Vary the target dimension on rolled-back drafts without mapping a source account."""
    if not __debug__ or env.cr.dbname not in (CERRO_NATIVE, CERRO_CE, CERRO_REVIEW):
        raise ValueError('Use the isolated Cerro payroll restores.')
    accounts = env['account.analytic.account'].with_user(7)
    company = accounts.env.company
    accounts = accounts.with_context(allowed_company_ids=[company.id])
    choices = accounts.search([('company_id', 'in', [False, company.id])], order='id').ids
    if not choices:
        raise ValueError('No original analytical account is available to the payroll operator.')
    return {'database': env.cr.dbname, 'input_digest': digest(fixture),
            'trials': [replay_cerro(env, fixture, trial_analytic_id=account_id, trial_tax=trial_tax)
                       for account_id in choices]}
