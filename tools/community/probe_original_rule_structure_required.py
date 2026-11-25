"""Verify primary rule ownership and its corresponding OCA membership."""
from uuid import uuid4

from lxml import etree
from odoo.fields import Command

from probe_original_structure_required import rejected, require_private_pair


def check_rule_fields(env, community):
    rule = env['hr.salary.rule']
    for name, ident in (('category_id', 8306), ('code', 8302)):
        original = env.ref(f'hr_payroll.field_hr_salary_rule__{name}')
        assert (original.id, original.model, original.name, original.required) == (
            ident, rule._name, name, True)
        assert rule._fields[name].required
    category = rule._fields['category_id']
    assert category.comodel_name == 'hr.salary.rule.category' and category.ondelete == 'restrict'
    env.cr.execute("""
        SELECT a.attname, a.attnotnull, c.confdeltype, c.convalidated
          FROM pg_attribute a
          LEFT JOIN pg_constraint c ON c.conrelid = a.attrelid
               AND c.conkey = ARRAY[a.attnum] AND c.contype = 'f'
               AND c.confrelid = 'hr_salary_rule_category'::regclass
         WHERE a.attrelid = 'hr_salary_rule'::regclass
           AND a.attname IN ('category_id', 'code') AND NOT a.attisdropped
         ORDER BY a.attname
    """)
    assert env.cr.fetchall() == [('category_id', True, 'r', True), ('code', True, None, None)]
    if community:
        line = env['hr.payslip.line']
        assert not line._fields['category_id'].required
        assert line._fields['code'].required
        env.cr.execute("""
            SELECT a.attname, a.attnotnull, c.confdeltype, c.convalidated
              FROM pg_attribute a
              LEFT JOIN pg_constraint c ON c.conrelid = a.attrelid
                   AND c.conkey = ARRAY[a.attnum] AND c.contype = 'f'
                   AND c.confrelid = 'hr_salary_rule_category'::regclass
             WHERE a.attrelid = 'hr_payslip_line'::regclass
               AND a.attname IN ('category_id', 'code') AND NOT a.attisdropped
             ORDER BY a.attname
        """)
        assert env.cr.fetchall() == [('category_id', False, 'n', True), ('code', True, None, None)]


def run(env, database):
    require_private_pair(env, database)
    rule = env['hr.salary.rule'].with_context(active_test=False)
    field = rule._fields['struct_id']
    assert field.required and field.comodel_name == 'hr.payroll.structure' and field.ondelete == 'restrict'
    original = env.ref('hr_payroll.field_hr_salary_rule__struct_id')
    assert original.id == 8303 and original.model == 'hr.salary.rule' and original.name == 'struct_id' and original.required
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
    check_rule_fields(env, community)
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

    # Use the original operator and existing masters for the temporary records.
    rule = rule.with_user(7)
    if community:
        view = rule.env.ref('payroll.hr_salary_rule_view_form')
        arch = etree.fromstring(rule.get_view(view_id=view.id, view_type='form')['arch'].encode())
        selectors = arch.xpath("//field[@name='struct_id' and not(@invisible) and not(@readonly) and not(@column_invisible)]")
        assert len(selectors) == 1 and not selectors[0].xpath('ancestor::*[@invisible or @readonly]')
        for name in ('category_id', 'code'):
            selectors = arch.xpath("//field[@name=$name and @required='1' and not(@readonly)]", name=name)
            assert len(selectors) == 1 and not selectors[0].xpath('ancestor::*[@invisible or @readonly]')
    structure = rule.env['hr.payroll.structure']
    template = structure.search([('country_id', '=', False), ('rule_ids', '!=', False)], order='id', limit=1)
    categories = template.rule_ids.mapped('category_id').sorted('id')[:2]
    assert template.type_id and len(categories) == 2
    key = 'STEP_' + uuid4().hex
    values = {'name': key, 'code': key, 'category_id': categories[0].id, 'amount_select': 'fix'}
    if 'company_id' in rule._fields:
        values['company_id'] = template.company_id.id
    if 'country_id' in rule._fields and not rule._fields['country_id'].related:
        values['country_id'] = template.country_id.id
    fixture_names = [key + suffix for suffix in ('_A', '_B')]

    def check_owner(record, owner):
        record.flush_recordset(['struct_id'])
        env.cr.execute('SELECT struct_id FROM hr_salary_rule WHERE id=%s', (record.id,))
        assert env.cr.fetchall() == [(owner.id,)]
        assert record in owner.rule_ids
        if community:
            owner.flush_recordset(['rule_ids'])
            env.cr.execute('SELECT struct_id FROM hr_structure_salary_rule_rel WHERE rule_id=%s', (record.id,))
            assert env.cr.fetchall() == [(owner.id,)]

    def clear_field(record, name):
        record.write({name: False})
        record.flush_recordset([name])

    try:
        # The anchor guards existing structure rows, including write_date.
        # Creating and moving a rule updates M2M through those ORM writes.
        structure_values = {'type_id': template.type_id.id, 'country_id': template.country_id.id}
        if 'company_id' in structure._fields:
            structure_values['company_id'] = template.company_id.id
        fixtures = [dict(structure_values, name=name) for name in fixture_names]
        if 'code' in structure._fields:
            for fixture in fixtures:
                fixture['code'] = fixture['name']
        first, second = structure.create(fixtures)
        values['struct_id'] = first.id
        for name in ('struct_id', 'category_id', 'code'):
            rejected(env.cr, lambda: rule.create(dict(values, **{name: False})).flush_recordset([name]),
                     'hr_salary_rule', name)
        record = rule.create(values)
        check_owner(record, first)
        assert record.code == key and record.category_id == categories[0]
        record.write({'struct_id': second.id, 'category_id': categories[1].id, 'code': key + '_EDIT'})
        check_owner(record, second)
        assert record not in first.rule_ids
        for name in ('struct_id', 'category_id', 'code'):
            rejected(env.cr, lambda: clear_field(record, name), 'hr_salary_rule', name)
        check_owner(record, second)
        env.cr.execute('SELECT category_id, code FROM hr_salary_rule WHERE id=%s', (record.id,))
        assert env.cr.fetchall() == [(categories[1].id, key + '_EDIT')]
        if community:
            rejected(env.cr, lambda: second.write({'rule_ids': [Command.unlink(record.id)]}),
                     'hr_salary_rule', 'struct_id', 'Move the rule primary structure')
            check_owner(record, second)
    finally:
        env.cr.rollback()
    assert not rule.search_count([('name', '=', key)])
    assert not structure.search_count([('name', 'in', fixture_names)])
    return {'database': database, 'operator_uid': rule.env.uid, 'original_field_id': original.id,
            'required': True, 'not_null': True,
            'validated_restrict_fk': True, 'original_structure_type_id': template.type_id.id,
            'valid_create_and_primary_move': True, 'missing_create_and_edit_rejected': True,
            'category_and_code_field_ids': [8306, 8302],
            'valid_category_and_code_edit': True, 'empty_category_and_code_rejected': True,
            'community_line_storage_preserved': community,
            'community_form_category_and_code_required': community,
            'community_editable_structure_selector': community,
            'community_membership_reconciled': community, 'fixture_rolled_back': True}
