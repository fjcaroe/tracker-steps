"""Read SyS original rule owners and company journals as the payroll operator."""
import re


def probe(shell_env, company_id, uid):
    from odoo import api

    assert re.fullmatch(r'COMMUNITY_SYS_PREVIRED_COHORT_[A-Z0-9_]{1,32}', shell_env.cr.dbname)
    assert type(uid) is int and uid > 1 and type(company_id) is int and company_id > 0
    with shell_env.registry.cursor() as cr:
        cr.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
        env = api.Environment(cr, uid, {'allowed_company_ids': [company_id], 'active_test': False})
        assert not env.su and env.company.id == company_id
        structures = env['hr.payroll.structure']
        assert structures._fields['rule_ids'].type == 'one2many'
        assert structures._fields['rule_ids'].inverse_name == 'struct_id'
        assert structures._fields['journal_id'].company_dependent
        for model, fields in [('hr.payroll.structure', ['type_id']), ('hr.payslip', ['name']),
                              ('hr.salary.rule', ['code', 'category_id']), ('hr.salary.rule.category', ['code']),
                              ('hr.contract', ['income_tax_type', 'work_schedule_id'])]:
            assert all(env[model]._fields[name].required for name in fields)
        rules = env['hr.salary.rule']
        assert rules._fields['struct_id'].required and rules._fields['struct_id'].ondelete == 'restrict'
        slips = env['hr.payslip']
        assert slips._fields['journal_id'].related == 'struct_id.journal_id' and not slips._fields['journal_id'].store
        cr.execute("""SELECT struct_id,id FROM hr_salary_rule ORDER BY struct_id,id""")
        pairs = set(cr.fetchall())
        cr.execute("""SELECT struct_id,rule_id FROM hr_structure_salary_rule_rel""")
        assert set(cr.fetchall()) == pairs
        original = structures.browse(sorted({structure for structure, _ in pairs}))
        original.check_access('read')
        original.check_field_access_rights('read', ['rule_ids', 'journal_id'])
        original_rules = rules.browse(sorted({rule for _, rule in pairs}))
        original_rules.check_access('read')
        original_rules.check_field_access_rights('read', ['struct_id'])
        assert pairs == {(structure.id, rule.id) for structure in original for rule in structure.rule_ids}
        assert pairs == {(rule.struct_id.id, rule.id) for rule in original_rules}
        batch = slips.search([('company_id', '=', company_id), ('date_from', '=', '2026-10-01'),
                              ('date_to', '=', '2026-10-31'), ('state', 'in', ['done', 'paid'])])
        batch.check_field_access_rights('read', ['struct_id', 'journal_id'])
        assert len(batch) == 5
        for slip in batch:
            assert slip.struct_id.journal_id == slip.journal_id
        return {'uid': uid, 'rules': len(original_rules), 'structures': len(original), 'slips': len(batch),
                'required_original_fields': 7}
