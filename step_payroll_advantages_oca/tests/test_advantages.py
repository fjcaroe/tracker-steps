"""Real OCA advantages, calculation, quantity/rate, accounting and normal ACL."""
from unittest import TestCase
from unittest.mock import patch

from odoo import api, Command, fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import TransactionCase, tagged
from odoo.addons.step_simpledigital_oca_base.tests.report_fixture import StoredReportFixture


@tagged('post_install', '-at_install')
class ContractAdvantageCase(StoredReportFixture, TransactionCase):
    def setUp(self):
        super().setUp()
        self.actor.write({'groups_id': [Command.link(self.env.ref('account.group_account_manager').id)]})
        self.scope = api.Environment(self.env.cr, self.actor.id,
            dict(self.scope.context, allowed_company_ids=self.company.ids), su=False)
        self.contract = self.contract.with_env(self.scope)
        self.structure = self.structure.with_env(self.scope)
        self.journal = self.scope['account.journal'].create({'name': 'Private advantage salary', 'code': 'PAV',
            'type': 'general', 'company_id': self.company.id})
        self.debit = self.scope['account.account'].create({'name': 'Private advantage expense', 'code': '936001',
            'account_type': 'expense', 'company_ids': [Command.set(self.company.ids)]})
        self.credit = self.scope['account.account'].create({'name': 'Private advantage debt', 'code': '936002',
            'account_type': 'liability_current', 'company_ids': [Command.set(self.company.ids)]})
        self.contract.journal_id = self.journal
        self.template = self.scope['hr.contract.advantage.template'].create({'name': 'Private actual advantage',
            'code': 'PRIVATE_ADV', 'lower_bound': 0, 'upper_bound': 100, 'default_value': 25.5})
        self.advantage = self.scope['hr.contract.advantage'].create({'contract_id': self.contract.id,
            'advantage_template_id': self.template.id, 'amount': 25.5})
        self.rule = self.scope['hr.salary.rule'].create({'name': 'Private actual advantage result', 'code': 'PRIVATE_ADV_RESULT',
            'struct_id': self.structure.id, 'company_id': self.company.id, 'category_id': self.categories['others'].id,
            'sequence': 50, 'condition_select': 'none', 'amount_select': 'code', 'quantity': '3.0',
            'amount_python_compute': 'result = current_contract.advantages.PRIVATE_ADV\nresult_qty = 3.0\nresult_rate = 80.0',
            'account_debit': self.debit.id, 'account_credit': self.credit.id})
        self.env['ir.sequence'].create({'name': 'Private advantage numbering', 'code': 'salary.slip',
            'company_id': self.company.id, 'implementation': 'no_gap', 'prefix': 'PRIVATE/ADV/'})

    def _slip(self):
        return self.scope['hr.payslip'].create({'name': 'Private actual advantage payroll',
            'number': 'PRIVATE/ADV/FIXTURE', 'employee_id': self.employee.id, 'company_id': self.company.id,
            'contract_id': self.contract.id, 'struct_id': self.structure.id,
            'date_from': fields.Date.today().replace(day=1), 'date_to': fields.Date.end_of(fields.Date.today(), 'month')})

    def _snapshot(self, slips):
        self.env.flush_all()
        result = {}
        for table, inverse, ids in (('hr_payslip', 'id', slips.ids), ('hr_payslip_line', 'slip_id', slips.ids),
                ('hr_payslip_worked_days', 'payslip_id', slips.ids), ('hr_payslip_input', 'payslip_id', slips.ids),
                ('account_move', 'id', slips.move_id.ids), ('account_move_line', 'move_id', slips.move_id.ids)):
            self.env.cr.execute('SELECT to_jsonb(t) FROM ' + table + ' t WHERE ' + inverse + '=ANY(%s) ORDER BY id', (ids,))
            result[table] = self.env.cr.fetchall()
        return result

    def test_real_provider_quantity_rate_amounts_form_and_accounting(self):
        self.assertFalse(self.scope.su)
        self.assertNotIn('hr.contract.salary.benefit', self.scope.registry)
        slip = self._slip()
        context = slip.get_current_contract_dict(self.contract, self.contract)
        self.assertEqual(context['advantages'].PRIVATE_ADV, 25.5)
        slip.compute_sheet()
        line = slip.line_ids.filtered(lambda row: row.code == 'PRIVATE_ADV_RESULT')
        expected = self.company.currency_id.round(25.5 * 3 * .8)
        self.assertEqual((line.amount, line.quantity, line.rate, line.total), (25.5, 3, 80, expected))
        slip.action_payslip_done()
        self.assertTrue(slip.move_id)
        self.assertEqual(sum(slip.move_id.line_ids.mapped('balance')), 0)
        self.assertEqual(sum(slip.move_id.line_ids.mapped('debit')), expected)
        view = self.scope['hr.contract'].get_view(view_id=self.scope.ref('hr_contract.hr_contract_view_form').id, view_type='form')
        self.assertIn('advantages_ids', view['arch'])
        for name in ('advantage_template_id', 'advantage_template_code', 'amount'):
            self.assertIn(name, view['arch'])
        template_view = self.scope['hr.contract.advantage.template'].get_view(view_type='form')
        self.assertIn('lower_bound', template_view['arch'])
        self.assertIn('upper_bound', template_view['arch'])

    def test_real_onchange_and_bounds_keep_explicit_zero_and_negative_values(self):
        preview = self.scope['hr.contract.advantage'].new({'contract_id': self.contract.id,
            'advantage_template_id': self.template.id})
        preview._onchange_advantage_template_id()
        self.assertEqual(preview.amount, 25.5)
        for amount in (-1, 101):
            with TestCase.assertRaises(self, ValidationError):
                self.advantage.write({'amount': amount})
            self.assertEqual(self.advantage.amount, 25.5)
        self.template.write({'lower_bound': 10})
        self.advantage.amount = 0
        slip = self._slip()
        slip.compute_sheet()
        self.assertEqual(slip.line_ids.filtered(lambda row: row.code == 'PRIVATE_ADV_RESULT').total, 0)
        self.template.write({'lower_bound': -100})
        self.advantage.amount = -25.5
        slip.compute_sheet()
        self.assertEqual(slip.line_ids.filtered(lambda row: row.code == 'PRIVATE_ADV_RESULT').total,
            self.company.currency_id.round(-25.5 * 3 * .8))

    def test_hidden_physical_rows_and_templates_block_warm_sudo_before_any_batch_line(self):
        first, second = self._slip(), self._slip()
        before = self._snapshot(first | second)
        self.advantage.sudo().read(['amount', 'advantage_template_id'])
        rule = self.env['ir.rule'].create({'name': 'Private hidden actual advantage',
            'model_id': self.env['ir.model']._get_id('hr.contract.advantage'),
            'domain_force': "[('id','!=',%s)]" % self.advantage.id})
        with TestCase.assertRaises(self, AccessError):
            (first | second).sudo().compute_sheet()
        self.assertEqual(self._snapshot(first | second), before)
        rule.unlink()
        rule = self.env['ir.rule'].create({'name': 'Private hidden advantage template',
            'model_id': self.env['ir.model']._get_id('hr.contract.advantage.template'),
            'domain_force': "[('id','!=',%s)]" % self.template.id})
        with TestCase.assertRaises(self, AccessError):
            first.sudo().get_current_contract_dict(self.contract, self.contract)
        self.assertEqual(self._snapshot(first | second), before)

    def test_field_acl_and_internal_user_cannot_read_or_mutate_through_sudo(self):
        slip = self._slip()
        before = self._snapshot(slip)
        self.advantage.sudo().read(['amount'])
        for field in (self.scope['hr.contract.advantage']._fields['amount'],
                self.scope['hr.contract.advantage.template']._fields['upper_bound']):
            with patch.object(field, 'groups', 'base.group_system'):
                with TestCase.assertRaises(self, AccessError):
                    slip.sudo().compute_sheet()
        self.assertEqual(self._snapshot(slip), before)
        user = self.env['res.users'].with_context(no_reset_password=True).create({'name': 'Private advantage internal',
            'login': 'private-advantage-internal', 'company_id': self.company.id,
            'company_ids': [Command.set(self.company.ids)], 'groups_id': [Command.set(self.env.ref('base.group_user').ids)]})
        for records in (self.advantage, self.template):
            with TestCase.assertRaises(self, AccessError):
                records.with_user(user).sudo().read()
            with TestCase.assertRaises(self, AccessError):
                records.with_user(user).sudo().write({'amount': 5} if records == self.advantage else {'code': 'FORBIDDEN'})

    def test_duplicate_codes_and_missing_sql_values_never_become_last_row_or_zero(self):
        slip = self._slip()
        duplicate = self.template.copy({'name': 'Private duplicate code'})
        extra = self.scope['hr.contract.advantage'].create({'contract_id': self.contract.id,
            'advantage_template_id': duplicate.id, 'amount': 0})
        before = self._snapshot(slip)
        with TestCase.assertRaisesRegex(self, UserError, 'unambiguous'):
            slip.compute_sheet()
        self.assertEqual(self._snapshot(slip), before)
        extra.unlink()
        self.advantage.flush_recordset(['amount'])
        self.env.cr.execute('UPDATE hr_contract_advantage SET amount=NULL WHERE id=%s', (self.advantage.id,))
        self.advantage.invalidate_recordset(['amount'])
        self.assertEqual(self.advantage.amount, 0)
        with TestCase.assertRaisesRegex(self, UserError, 'missing'):
            slip.sudo().compute_sheet()
        self.env.cr.execute('SELECT amount FROM hr_contract_advantage WHERE id=%s', (self.advantage.id,))
        self.assertIsNone(self.env.cr.fetchone()[0])
        self.assertEqual(self._snapshot(slip), before)

    def test_changed_template_limits_are_rechecked_before_posting(self):
        slip = self._slip()
        slip.compute_sheet()
        before = self._snapshot(slip)
        self.template.upper_bound = 10
        with TestCase.assertRaisesRegex(self, UserError, 'limits'):
            slip.action_payslip_done()
        self.assertEqual(self._snapshot(slip), before)
        self.assertFalse(slip.move_id)
        with TestCase.assertRaisesRegex(self, UserError, 'still uses this template'):
            self.template.unlink()
        self.template.upper_bound = 100
        slip.action_payslip_done()
        self.assertEqual(slip.state, 'done')

    def test_closed_history_has_no_live_advantage_reconstruction(self):
        slip = self._slip()
        slip.compute_sheet()
        slip.action_payslip_done()
        before = self._snapshot(slip)
        self.advantage.amount = 50
        self.template.code = 'PRIVATE_FUTURE_ADV'
        for operation in (lambda: slip.sudo().compute_sheet(), lambda: slip.sudo().action_payslip_done(),
                lambda: slip.sudo().get_current_contract_dict(self.contract, self.contract)):
            with TestCase.assertRaises(self, UserError):
                operation()
        slip._get_line_values(['PRIVATE_ADV_RESULT'])
        self.assertEqual(self._snapshot(slip), before)

    def test_company_scope_covers_direct_reads_copy_references_and_unlink(self):
        foreign_company = self.env['res.company'].create({'name': 'Private foreign advantage company',
            'country_id': self.env.ref('base.cl').id})
        author = self.env['hr.contract'].with_company(foreign_company).env
        employee = author['hr.employee'].create({'name': 'Private foreign advantage employee', 'company_id': foreign_company.id})
        values = {'name': 'Private foreign advantage contract', 'employee_id': employee.id, 'company_id': foreign_company.id,
            'date_start': fields.Date.today().replace(day=1), 'wage': 1, 'structure_type_id': self.kind.id, 'state': 'open'}
        contract = author['hr.contract'].create(values)
        with TestCase.assertRaises(self, AccessError):
            self.advantage.sudo().copy({'contract_id': contract.id})
        actor = self.env['res.users'].with_context(no_reset_password=True).create({'name': 'Private foreign advantage manager',
            'login': 'private-foreign-advantage-manager', 'company_id': foreign_company.id,
            'company_ids': [Command.set(foreign_company.ids)], 'groups_id': [Command.set([self.env.ref(alias).id for alias in
                ('base.group_user', 'payroll.group_payroll_manager', 'hr.group_hr_manager')])]})
        foreign_scope = api.Environment(self.env.cr, actor.id, dict(self.env.context,
            allowed_company_ids=foreign_company.ids), su=False)
        foreign = foreign_scope['hr.contract.advantage'].create({'contract_id': contract.id,
            'advantage_template_id': self.template.id, 'amount': 5})
        before = foreign.amount
        foreign = foreign.with_env(self.scope)
        for operation in (lambda: foreign.sudo().read(['amount']), lambda: foreign.sudo().copy_data(),
                lambda: foreign.sudo().write({'amount': 6}), lambda: foreign.sudo().unlink()):
            with TestCase.assertRaises(self, AccessError):
                operation()
        self.assertEqual(foreign.with_env(foreign_scope).amount, before)
        with TestCase.assertRaisesRegex(self, UserError, 'still uses this contract'):
            contract.with_env(foreign_scope).unlink()

    def test_nonfinite_or_reversed_limits_and_changed_template_fail_atomically(self):
        names = ['contract_id', 'advantage_template_id', 'amount']
        before = self.advantage.read(names)
        for amount in (float('inf'), float('-inf'), float('nan')):
            with TestCase.assertRaises(self, ValidationError):
                self.advantage.write({'amount': amount})
            self.assertEqual(self.advantage.read(names), before)
        other = self.template.copy({'code': 'PRIVATE_LIMITS', 'lower_bound': 0, 'upper_bound': 10})
        with TestCase.assertRaises(self, ValidationError):
            self.advantage.write({'advantage_template_id': other.id})
        self.assertEqual(self.advantage.read(names), before)
        self.template.write({'lower_bound': 100, 'upper_bound': 0})
        slip = self._slip()
        original = self._snapshot(slip)
        with TestCase.assertRaisesRegex(self, UserError, 'ordered limits'):
            slip.compute_sheet()
        self.assertEqual(self._snapshot(slip), original)

    def test_real_second_rule_failure_rolls_back_both_drafts(self):
        first, second = self._slip(), self._slip()
        self.rule.amount_python_compute = 'result = current_contract.advantages.PRIVATE_ADV / (2 if payslip.id == %s else 0)' % first.id
        before = self._snapshot(first | second)
        with TestCase.assertRaises(self, UserError):
            (first | second).compute_sheet()
        self.assertEqual(self._snapshot(first | second), before)
        self.assertEqual(first.state, 'draft')
        self.assertEqual(second.state, 'draft')
