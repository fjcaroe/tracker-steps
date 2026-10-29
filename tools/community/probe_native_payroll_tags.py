"""Observe original payroll tag behavior in a coordinator-owned private clone.

No Enterprise implementation is imported, inspected or copied.  The existing
real-engine fixture supplies a normal payroll/accounting actor. All fixture
business writes are rolled back; only the requested private JSON is retained.
The coordinator owns backup, source admission, database prefix and the lease.
"""
import json
from pathlib import Path


class _RollbackObservation(Exception):
    def __init__(self, result):
        self.result = result


def observe(env, output):
    from odoo import Command
    from odoo.addons.step_payroll_contracts.testing import PayrollContractMixin
    from unittest.mock import patch

    env.cr.execute("SELECT name,state FROM ir_module_module WHERE name IN ('hr_payroll','hr_payroll_account')")
    if dict(env.cr.fetchall()) != {'hr_payroll': 'installed', 'hr_payroll_account': 'installed'}:
        raise ValueError('This observation requires the actual installed native payroll/accounting reference.')
    for name in ('debit_tag_ids', 'credit_tag_ids'):
        if name not in env['hr.salary.rule']._fields:
            raise ValueError('The original rule tag contract is unavailable.')

    class FixtureRoot:
        @classmethod
        def setUpClass(cls):
            pass

    class NativeTagFixture(PayrollContractMixin, FixtureRoot):
        payroll_group = 'hr_payroll.group_hr_payroll_manager'
        oca = False

    NativeTagFixture.env = env
    try:
        with env.cr.savepoint():
            # Settle the actual company chart callbacks, as TransactionCase
            # normally does. No engine, permission or financial result is
            # mocked; the trusted author still creates the real company.
            company_class = type(env['res.company'])
            original_create = company_class.create
            def create_ready_company(records, values):
                company = original_create(records, values)
                records.env.cr.flush()
                return company
            with patch.object(company_class, 'create', create_ready_company):
                NativeTagFixture.setUpClass()
            fixture = NativeTagFixture()
            scope = fixture.scope
            if scope.su:
                raise AssertionError('The real payroll operations must use the ordinary fixture actor.')
            tags = env['account.account.tag'].create([
                {'name': '+Private original payroll debit grid', 'applicability': 'taxes', 'country_id': fixture.company.country_id.id},
                {'name': '+Private original payroll credit grid', 'applicability': 'taxes', 'country_id': fixture.company.country_id.id},
            ]).with_env(scope)
            tags.check_access('read')
            fixture.rule.write({'debit_tag_ids': [Command.set(tags[0].ids)],
                                'credit_tag_ids': [Command.set(tags[1].ids)], 'amount_select': 'fix'})

            metadata = []
            for model_name in ('hr.salary.rule', 'hr.payslip.line'):
                model = scope[model_name]
                for name in ('debit_tag_ids', 'credit_tag_ids'):
                    field = model._fields[name]
                    domain = field.get_domain_list(model)
                    metadata.append({'model': model_name, 'name': name, 'type': field.type,
                        'comodel': field.comodel_name, 'store': field.store, 'readonly': field.readonly,
                        'copy': field.copy, 'related': field.related, 'computed': bool(field.compute),
                        'relation': field.relation, 'column1': field.column1, 'column2': field.column2,
                        'domain': domain, 'domain_expression': field.domain if isinstance(field.domain, str) else None})
            observations = []
            for index, (amount, credit_note) in enumerate(((100, False), (-100, False), (100, True), (-100, True)), 1):
                fixture.rule.amount_fix = amount
                slip = fixture.slip(amount=0)
                slip.write({'number': 'PRIVATE/TAGS/REFERENCE/%s' % index, 'credit_note': credit_note})
                slip.compute_sheet()
                credit_note_before = slip.credit_note
                stored_before = slip.line_ids.read(['id', 'salary_rule_id', 'amount', 'quantity', 'rate', 'total'])
                computed_before = slip.line_ids.read(['id', 'debit_tag_ids', 'credit_tag_ids'])
                slip.action_payslip_done()
                observations.append({'amount': amount, 'credit_note': credit_note,
                    'credit_note_before': credit_note_before, 'credit_note_after': slip.credit_note,
                    'normal_actor': not slip.env.su, 'state': slip.state, 'number': slip.number,
                    'salary_before': stored_before, 'line_tags_before': computed_before,
                    'salary_after': slip.line_ids.read(['id', 'salary_rule_id', 'amount', 'quantity', 'rate', 'total']),
                    'line_tags_after': slip.line_ids.read(['id', 'debit_tag_ids', 'credit_tag_ids']),
                    'move': slip.move_id.read(['id', 'state', 'journal_id', 'company_id']),
                    'move_lines': slip.move_id.line_ids.read(['id', 'account_id', 'debit', 'credit', 'balance', 'tax_tag_ids', 'tax_tag_invert'])})
            result = {'schema': 1, 'purpose': 'native-reference-observation', 'metadata': metadata,
                'fixture_account_ids': {'debit': fixture.debit.id, 'credit': fixture.credit.id},
                'fixture_tag_ids': {'debit': tags[0].id, 'credit': tags[1].id}, 'observations': observations,
                'business_fixture_rolled_back': True, 'engine_replaced': False,
                'equivalence_certified': False, 'production_cutover': False}
            raise _RollbackObservation(result)
    except _RollbackObservation as done:
        result = done.result
    Path(output).write_text(json.dumps(result, indent=2, default=str), encoding='utf-8')
    return result
