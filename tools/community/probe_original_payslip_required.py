"""Exercise original payslip and Simple Digital contract requirements on the private pair."""
from datetime import date
from uuid import uuid4

from lxml import etree
from odoo import Command
from odoo.exceptions import UserError

from probe_original_structure_required import rejected, require_private_pair


FIELDS = (
    ('hr.payslip', 'name', 8371, None),
    ('hr.payslip.input', 'input_type_id', 8476, 'hr.payslip.input.type'),
    ('hr.payslip.worked_days', 'work_entry_type_id', 8458, 'hr.work.entry.type'),
    ('hr.contract', 'income_tax_type', 9727, None),
    ('hr.contract', 'work_schedule_id', 9728, None),
)


def check_storage(env):
    for model, name, ident, relation in FIELDS:
        namespace = 'l10n_cl_simpledigital_payroll' if model == 'hr.contract' else 'hr_payroll'
        original = env.ref(f"{namespace}.field_{model.replace('.', '_')}__{name}")
        assert (original.id, original.model, original.name, original.required) == (ident, model, name, True)
        declaration = env[model]._fields[name]
        assert declaration.required and declaration.store
        if relation:
            assert declaration.comodel_name == relation and declaration.ondelete == 'restrict'
        env.cr.execute("""
            SELECT a.attnotnull, c.confdeltype, c.convalidated, c.confrelid::regclass::text
            FROM pg_attribute a
            LEFT JOIN pg_constraint c ON c.conrelid=a.attrelid AND c.conkey=ARRAY[a.attnum] AND c.contype='f'
            WHERE a.attrelid=%s::regclass AND a.attname=%s AND NOT a.attisdropped
        """, (env[model]._table, name))
        expected = (True, 'r', True, env[relation]._table) if relation else (True, None, None, None)
        assert env.cr.fetchall() == [expected], (model, name)


def clear_field(record, name):
    record.write({name: False})
    record.flush_recordset([name])


def check_line(slip, model, field, kinds, values, guard):
    lines = slip.env[model]
    supplied = dict(values, payslip_id=slip.id)
    if guard:
        supplied['contract_id'] = slip.contract_id.id
    missing = dict(supplied, **{field: False})
    if guard:
        missing['code'] = kinds[0].code
    rejected(slip.env.cr, lambda: lines.create(missing).flush_recordset([field]), lines._table, field)
    record = lines.create(dict(supplied, **{field: kinds[0].id}))
    assert record[field] == kinds[0]
    record.write({field: kinds[1].id})
    record.flush_recordset([field])
    rejected(slip.env.cr, lambda: clear_field(record, field), lines._table, field, guard)
    assert record[field] == kinds[1] and record.code == kinds[1].code


def run(env, database):
    require_private_pair(env, database)
    check_storage(env)
    community = '_HANDOVER_' in database
    slip_model = env['hr.payslip'].with_user(7).with_context(tracking_disable=True)
    original_company = slip_model.env.company
    employee = slip_model.env['hr.employee'].search([
        ('company_id', '=', original_company.id), ('resource_calendar_id', '!=', False)], order='id', limit=1)
    structure = slip_model.env['hr.payroll.structure'].search([('country_id', '=', False)], order='id', limit=1)
    inputs = slip_model.env['hr.payslip.input.type'].search([('country_id', '=', False)], order='id', limit=2)
    attendance = slip_model.env.ref('hr_work_entry.work_entry_type_attendance')
    other = slip_model.env['hr.work.entry.type'].search([('id', '!=', attendance.id)], order='id', limit=1)
    assert employee and structure and len(inputs) == 2 and attendance and other
    key = 'STEP_' + uuid4().hex
    start, stop = date(2026, 11, 2), date(2026, 11, 6)
    contract_model = env['hr.contract'].with_context(tracking_disable=True).with_company(original_company)
    values = {'name': key, 'employee_id': employee.id, 'company_id': original_company.id, 'wage': 100,
        'date_start': start, 'resource_calendar_id': employee.resource_calendar_id.id,
        'structure_type_id': structure.type_id.id}
    if 'struct_id' in contract_model._fields:
        values['struct_id'] = structure.id
    try:
        contracts = ('income_tax_type', 'work_schedule_id')
        for field in contracts:
            rejected(env.cr, lambda: contract_model.create(dict(values, **{field: False})).flush_recordset([field]),
                     'hr_contract', field)
        contract = contract_model.create(values)
        for field in contracts:
            options = contract._fields[field].get_values(contract.env)
            assert contract[field] in options
            new_value = next(option for option in options if option != contract[field])
            contract.write({field: new_value})
            contract.flush_recordset([field])
            rejected(env.cr, lambda: clear_field(contract, field), 'hr_contract', field)
            assert contract[field] == new_value
        header = {'employee_id': employee.id, 'contract_id': contract.id, 'company_id': original_company.id,
            'struct_id': structure.id, 'date_from': start, 'date_to': stop}
        rejected(env.cr, lambda: slip_model.create(dict(header, name=False)).flush_recordset(['name']), 'hr_payslip', 'name')
        if community:
            view = slip_model.env.ref('payroll.hr_payslip_view_form')
            arch = etree.fromstring(slip_model.get_view(view_id=view.id, view_type='form')['arch'].encode())
            for container, selector in (('input_line_ids', 'input_type_id'), ('worked_days_line_ids', 'work_entry_type_id')):
                for subview in ('list', 'form'):
                    assert len(arch.xpath("//field[@name=$container]/*[name()=$view]//field[@name=$field]",
                                         container=container, view=subview, field=selector)) == 1
            generated = slip_model.with_context(contract=True).get_payslip_vals(
                start, stop, employee.id, contract.id, [structure.id])['value']
            assert generated['name'] and generated['contract_id'] == contract.id
            assert generated['worked_days_line_ids'] and all(row['work_entry_type_id'] for row in generated['worked_days_line_ids'])
            slip = slip_model.create(dict(header, name=generated['name'],
                worked_days_line_ids=[Command.create(row) for row in generated['worked_days_line_ids']],
                input_line_ids=[Command.create(row) for row in generated['input_line_ids']]))
            assert attendance in slip.worked_days_line_ids.work_entry_type_id
        else:
            slip = slip_model.create(dict(header, name=key))
        slip.write({'name': key + '_EDIT'})
        slip.flush_recordset(['name'])
        rejected(env.cr, lambda: clear_field(slip, 'name'), 'hr_payslip', 'name')
        assert slip.name == key + '_EDIT'
        check_line(slip, 'hr.payslip.input', 'input_type_id', inputs, {'amount': 1},
                   'A typed input must retain its master relation.' if community else None)
        check_line(slip, 'hr.payslip.worked_days', 'work_entry_type_id', attendance | other,
                   {'number_of_days': 1, 'number_of_hours': 1},
                   'A typed worked day must retain its master relation.' if community else None)
        if community:
            slip.write({'state': 'done'})
            try:
                with env.cr.savepoint():
                    slip.write({'name': key + '_FORBIDDEN'})
            except UserError as exc:
                assert 'Closed payroll history' in str(exc)
            else:
                raise AssertionError('A closed name was changed')
            assert slip.name == key + '_EDIT'
    finally:
        env.cr.rollback()
    assert not contract_model.search_count([('name', '=', key)])
    assert not slip_model.search_count([('name', '=', key + '_EDIT')])
    return {'database': database, 'operator_uid': slip_model.env.uid,
            'original_field_ids': [row[2] for row in FIELDS], 'required_orm_and_sql': True,
            'valid_create_and_edit': True, 'empty_create_and_edit_rejected': True,
            'community_generated_name_and_typed_attendance': community,
            'community_typed_selectors': community, 'community_closed_name_protected': community,
            'fixture_rolled_back': True}
