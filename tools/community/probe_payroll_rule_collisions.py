"""Black-box duplicate-code observations on private real engines; roll back fixtures."""
import json
from pathlib import Path
import re
from unittest import TestCase
from unittest.mock import patch


def exercise(env, output):
    from odoo.addons.step_payroll_contracts.testing import PayrollContractMixin
    assert re.fullmatch('(COMMUNITY_PAYROLL_API_|MANAGEMENT_QA_CERRO_PAYROLL_API_)[A-Za-z0-9_]+', env.cr.dbname)
    path = Path(output)
    assert str(path.resolve()).startswith('/opt/steps-validation/')

    class Fixture(PayrollContractMixin, TestCase):
        payroll_group = 'payroll.group_payroll_manager'

    Fixture.env = env
    model = type(env['res.company'])
    original = model.create

    def ready(records, values):
        result = original(records, values)
        records.env.cr.flush()
        return result

    try:
        with patch.object(model, 'create', ready):
            Fixture.setUpClass()
        case = Fixture()
        (case.structure.rule_ids - case.rule).unlink()
        scope = case.scope
        first_category = case.rule.category_id
        second_category = scope['hr.salary.rule.category'].create({'name': 'Private second category', 'code': 'PRIVATE_SECOND'})
        case.rule.write({'code': 'PRIVATE_COLLISION', 'sequence': 10, 'amount_python_compute': 'result = 10'})
        second = case.rule.copy({'name': 'Private second identity', 'sequence': 10,
                                 'category_id': second_category.id, 'amount_python_compute': 'result = 20'})
        for code, formula in [('PRIVATE_FIRST_READ', 'categories[\'PRIVATE_NET\']'),
                              ('PRIVATE_SECOND_READ', 'categories[\'PRIVATE_SECOND\']'),
                              ('PRIVATE_RULE_READ', 'result_rules[\'PRIVATE_COLLISION\'][\'total\']')]:
            case.rule.copy({'code': code, 'sequence': 20, 'category_id': scope['hr.salary.rule.category'].create(
                {'name': code, 'code': code}).id, 'amount_python_compute': 'result = ' + formula})
        observations = {}
        for name, values in [('same_sequence_distinct_categories', {}),
                             ('reverse_sequence', {'sequence': 5}),
                             ('same_category', {'sequence': 10, 'category_id': first_category.id}),
                             ('second_zero', {'amount_python_compute': 'result = 0'})]:
            if values:
                second.write(values)
            slip = case.slip()
            slip.compute_sheet()
            env.flush_all()
            env.cr.execute('SELECT code,salary_rule_id,total FROM hr_payslip_line WHERE slip_id=%s ORDER BY sequence,id', (slip.id,))
            observations[name] = [{'code': code, 'rule': 'first' if rule == case.rule.id else 'second' if rule == second.id else 'reader',
                                    'total': total} for code, rule, total in env.cr.fetchall()]
        result = {'database': env.cr.dbname, 'normal_actor': not scope.su, 'synthetic_only': True,
                  'fixtures_rolled_back': True, 'writes_to_source': False, 'financial_certified': False,
                  'observations': observations}
    finally:
        env.cr.rollback()
    path.write_text(json.dumps(result, indent=2), encoding='utf-8')
