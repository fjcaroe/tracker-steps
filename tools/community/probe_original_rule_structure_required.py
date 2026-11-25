"""Verify primary rule ownership and its corresponding OCA membership."""
from itertools import combinations
from uuid import uuid4

from lxml import etree
from odoo.fields import Command

from probe_original_structure_required import rejected, require_private_pair


def run(env, database):
    require_private_pair(env, database)
    rule = env['hr.salary.rule'].with_context(active_test=False)
    field = rule._fields['struct_id']
    assert field.required and field.comodel_name == 'hr.payroll.structure' and field.ondelete == 'restrict'
    env.cr.execute("""
        SELECT a.attnotnull, c.confdeltype, c.convalidated
          FROM pg_attribute a
          JOIN pg_constraint c ON c.conrelid = a.attrelid AND c.conkey = ARRAY[a.attnum]
         WHERE a.attrelid = 'hr_salary_rule'::regclass AND a.attname = 'struct_id'
           AND NOT a.attisdropped AND c.contype = 'f'
           AND c.confrelid = 'hr_payroll_structure'::regclass
    """)
    assert env.cr.fetchall() == [(True, 'r', True)]
    community = '_HANDOVER_' in database
    line_field = env['hr.payslip.line']._fields.get('struct_id')
    if community:
        assert line_field is not None and not line_field.required
        env.cr.execute("""
            SELECT attnotnull FROM pg_attribute
             WHERE attrelid = 'hr_payslip_line'::regclass AND attname = 'struct_id'
               AND NOT attisdropped
        """)
        assert env.cr.fetchall() == [(False,)]
    else:
        assert line_field is None

    # Use the original operator and keep the move within one existing scope.
    rule = rule.with_user(7)
    if community:
        view = rule.env.ref('payroll.hr_salary_rule_view_form')
        arch = etree.fromstring(rule.get_view(view_id=view.id, view_type='form')['arch'].encode())
        selectors = arch.xpath("//field[@name='struct_id' and not(@invisible) and not(@readonly)]")
        assert len(selectors) == 1 and not selectors[0].xpath('ancestor::*[@invisible or @readonly]')
    structures = rule.env['hr.payroll.structure'].search([], order='id')
    scope_fields = [name for name in ('company_id', 'country_id') if name in structures._fields]
    pair = next(((first, second) for first, second in combinations(structures, 2)
                 if all(first[name] == second[name] for name in scope_fields)), None)
    assert pair is not None, 'No two visible original structures share a scope'
    first, second = pair
    category = first.rule_ids.mapped('category_id').sorted('id')[:1]
    assert category
    key = 'STEP_' + uuid4().hex
    values = {'name': key, 'code': key, 'category_id': category.id, 'amount_select': 'fix'}
    if 'company_id' in rule._fields:
        values['company_id'] = first.company_id.id
    if 'country_id' in rule._fields and not rule._fields['country_id'].related:
        values['country_id'] = first.country_id.id

    def check_owner(record, owner):
        record.flush_recordset(['struct_id'])
        env.cr.execute('SELECT struct_id FROM hr_salary_rule WHERE id=%s', (record.id,))
        assert env.cr.fetchall() == [(owner.id,)]
        assert record in owner.rule_ids
        if community:
            structures.flush_recordset(['rule_ids'])
            env.cr.execute('SELECT struct_id FROM hr_structure_salary_rule_rel WHERE rule_id=%s', (record.id,))
            assert env.cr.fetchall() == [(owner.id,)]

    try:
        rejected(env.cr, lambda: rule.create(dict(values, struct_id=False)).flush_recordset(['struct_id']),
                 'hr_salary_rule', 'struct_id')
        record = rule.create(dict(values, struct_id=first.id))
        check_owner(record, first)
        record.write({'struct_id': second.id})
        check_owner(record, second)
        assert record not in first.rule_ids
        rejected(env.cr, lambda: record.write({'struct_id': False}).flush_recordset(['struct_id']),
                 'hr_salary_rule', 'struct_id')
        check_owner(record, second)
        if community:
            rejected(env.cr, lambda: second.write({'rule_ids': [Command.unlink(record.id)]}),
                     'hr_salary_rule', 'struct_id', 'Move the rule primary structure')
            check_owner(record, second)
    finally:
        env.cr.rollback()
    assert not rule.search_count([('code', '=', key)])
    return {'database': database, 'operator_uid': rule.env.uid, 'required': True, 'not_null': True,
            'validated_restrict_fk': True, 'original_structure_ids': [first.id, second.id],
            'valid_create_and_primary_move': True, 'missing_create_and_edit_rejected': True,
            'community_editable_structure_selector': community,
            'community_membership_reconciled': community, 'fixture_rolled_back': True}
