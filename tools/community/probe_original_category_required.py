"""Exercise original category writes with a rolled-back fixture on the pair."""
import re
from uuid import uuid4

from odoo.exceptions import ValidationError
from psycopg2.errors import NotNullViolation


def column_required(cr):
    cr.execute("SELECT attnotnull FROM pg_attribute WHERE attrelid = "
               "'hr_salary_rule_category'::regclass AND attname = 'code' AND NOT attisdropped")
    return cr.fetchone() == (True,)


def rejected(cr, operation):
    try:
        with cr.savepoint():
            operation()
    except NotNullViolation as exc:
        assert exc.diag.table_name == 'hr_salary_rule_category' and exc.diag.column_name == 'code'
    except ValidationError as exc:
        assert 'code' in str(exc).lower()
    else:
        raise AssertionError('Category write without a code succeeded')


def run(env, database):
    assert re.fullmatch(r'MANAGEMENT_QA_CERRO_PAYROLL_API_ORIGINAL_(HANDOVER|REFERENCE)_[A-Za-z0-9_]+', database)
    assert env.cr.dbname == database and column_required(env.cr)
    category = env['hr.salary.rule.category']
    assert category._fields['code'].required
    key = 'STEP_' + uuid4().hex

    def create_without_code():
        category.create({'name': key, 'code': False}).flush_recordset(['code'])

    def clear_code(record):
        record.write({'code': False})
        record.flush_recordset(['code'])

    try:
        rejected(env.cr, create_without_code)
        record = category.create({'name': key, 'code': key})
        record.write({'code': key + '_EDIT'})
        record.flush_recordset(['code'])
        rejected(env.cr, lambda: clear_code(record))
        env.cr.execute('SELECT code FROM hr_salary_rule_category WHERE id=%s', (record.id,))
        assert env.cr.fetchone() == (key + '_EDIT',)
    finally:
        env.cr.rollback()
    assert not category.search_count([('name', '=', key)])
    return {'database': database, 'required': True, 'not_null': True,
            'valid_create_and_edit': True, 'missing_create_and_edit_rejected': True,
            'fixture_rolled_back': True}
