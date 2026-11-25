"""Exercise the original structure type with existing masters on the private pair."""
import re
from uuid import uuid4

from odoo.exceptions import ValidationError
from psycopg2.errors import NotNullViolation


def rejected(cr, operation):
    try:
        with cr.savepoint():
            operation()
    except NotNullViolation as exc:
        assert exc.diag.table_name == 'hr_payroll_structure' and exc.diag.column_name == 'type_id'
    except ValidationError as exc:
        assert 'type_id' in str(exc)
    else:
        raise AssertionError('Structure write without a type succeeded')


def run(env, database):
    assert re.fullmatch(r'MANAGEMENT_QA_CERRO_PAYROLL_API_ORIGINAL_(HANDOVER|REFERENCE)_[A-Za-z0-9_]+', database)
    assert env.cr.dbname == database
    structure = env['hr.payroll.structure'].with_context(active_test=False)
    field = structure._fields['type_id']
    assert field.required and field.comodel_name == 'hr.payroll.structure.type' and field.ondelete == 'restrict'
    env.cr.execute("""
        SELECT a.attnotnull, c.confdeltype, c.convalidated
          FROM pg_attribute a
          JOIN pg_constraint c ON c.conrelid = a.attrelid AND c.conkey = ARRAY[a.attnum]
         WHERE a.attrelid = 'hr_payroll_structure'::regclass AND a.attname = 'type_id'
           AND NOT a.attisdropped AND c.contype = 'f'
           AND c.confrelid = 'hr_payroll_structure_type'::regclass
    """)
    assert env.cr.fetchall() == [(True, 'r', True)]

    # Take two global types already used by original structures. The
    # temporary structure never supplies or modifies a payroll master type.
    kinds = structure.search([('country_id', '=', False)]).mapped('type_id').filtered(
        lambda kind: not kind.country_id).sorted('id')[:2]
    assert len(kinds) == 2
    key = 'STEP_' + uuid4().hex
    values = {'name': key, 'country_id': False}
    if 'code' in structure._fields:
        values['code'] = key
    if 'company_id' in structure._fields:
        values['company_id'] = False

    def clear_type(record):
        record.write({'type_id': False})
        record.flush_recordset(['type_id'])

    try:
        rejected(env.cr, lambda: structure.create(dict(values, type_id=False)).flush_recordset(['type_id']))
        record = structure.create(dict(values, type_id=kinds[0].id))
        assert record.type_id == kinds[0]
        record.write({'type_id': kinds[1].id})
        record.flush_recordset(['type_id'])
        rejected(env.cr, lambda: clear_type(record))
        env.cr.execute('SELECT type_id FROM hr_payroll_structure WHERE id=%s', (record.id,))
        assert env.cr.fetchone() == (kinds[1].id,)
    finally:
        env.cr.rollback()
    assert not structure.search_count([('name', '=', key)])
    return {'database': database, 'required': True, 'not_null': True, 'validated_restrict_fk': True,
            'existing_type_ids': kinds.ids, 'valid_create_and_type_change': True,
            'missing_create_and_edit_rejected': True, 'fixture_rolled_back': True}
