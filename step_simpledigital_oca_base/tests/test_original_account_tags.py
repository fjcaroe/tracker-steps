"""Original tax-grid identity, ordinary access and real OCA journal entries."""
from unittest.mock import patch

from odoo import api, Command, fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import Form, TransactionCase, tagged


@tagged('post_install', '-at_install')
class OriginalAccountTagsCase(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({'name': 'Private original grid company',
            'country_id': cls.env.ref('base.cl').id, 'currency_id': cls.env.ref('base.CLP').id,
            'account_fiscal_country_id': cls.env.ref('base.cl').id})
        actor = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Private original grid payroll actor', 'login': 'private-original-grid-actor',
            'company_id': cls.company.id, 'company_ids': [Command.set(cls.company.ids)],
            'groups_id': [Command.set([cls.env.ref(name).id for name in (
                'base.group_user', 'payroll.group_payroll_manager', 'account.group_account_manager', 'hr.group_hr_manager')])]})
        cls.scope = api.Environment(cls.env.cr, actor.id, dict(cls.env.context, allowed_company_ids=cls.company.ids), su=False)
        cls.journal = cls.scope['account.journal'].create({'name': 'Private original grid journal', 'code': 'OGD',
            'type': 'general', 'company_id': cls.company.id})
        cls.debit = cls.scope['account.account'].create({'name': 'Private original grid cost', 'code': '940071',
            'account_type': 'expense', 'company_ids': [Command.set(cls.company.ids)]})
        cls.credit = cls.scope['account.account'].create({'name': 'Private original grid liability', 'code': '940072',
            'account_type': 'liability_current', 'company_ids': [Command.set(cls.company.ids)]})
        kind = cls.scope['hr.payroll.structure.type'].create({'name': 'Private original grid type'})
        cls.structure = cls.scope['hr.payroll.structure'].create({'name': 'Private original grid structure',
            'code': 'PRIVATE_ORIGINAL_GRID', 'type_id': kind.id, 'company_id': cls.company.id,
            'parent_id': False, 'journal_id': cls.journal.id})
        category = cls.scope['hr.salary.rule.category'].create({'name': 'Private original grid category',
            'code': 'PRIVATE_ORIGINAL_GRID', 'company_id': cls.company.id})
        cls.rule = cls.scope['hr.salary.rule'].create({'name': 'Private original grid rule', 'code': 'PRIVATE_ORIGINAL_GRID',
            'sequence': 1, 'company_id': cls.company.id, 'category_id': category.id, 'struct_id': cls.structure.id,
            'condition_select': 'none', 'amount_select': 'fix', 'amount_fix': 100.0,
            'account_debit': cls.debit.id, 'account_credit': cls.credit.id})
        # The actor processes payroll and reads tax grids; the fixture author
        # alone provisions configuration masters. No groups/ACL are expanded.
        cls.tags = cls.env['account.account.tag'].create([
            {'name': '+Private original debit grid', 'applicability': 'taxes', 'country_id': cls.company.country_id.id},
            {'name': '+Private original credit grid', 'applicability': 'taxes', 'country_id': cls.company.country_id.id},
            {'name': '+Private shared original grid', 'applicability': 'taxes', 'country_id': False},
        ]).with_env(cls.scope)
        cls.tags.check_access('read')
        cls.rule.write({'debit_tag_ids': [Command.set(cls.tags[0].ids)], 'credit_tag_ids': [Command.set(cls.tags[1].ids)]})
        employee = cls.scope['hr.employee'].create({'name': 'Private original grid employee', 'company_id': cls.company.id})
        values = {'name': 'Private original grid contract', 'employee_id': employee.id, 'company_id': cls.company.id,
            'state': 'open', 'date_start': fields.Date.today().replace(day=1), 'wage': 100.0,
            'structure_type_id': kind.id, 'struct_id': cls.structure.id, 'journal_id': cls.journal.id}
        if 'contract_type_id' in cls.scope['hr.contract']._fields:
            field = cls.scope['hr.contract']._fields['contract_type_id']
            values['contract_type_id'] = cls.scope[field.comodel_name].search([], limit=1).id
        cls.contract = cls.scope['hr.contract'].create(values)

    def _slip(self, credit_note=False):
        return self.scope['hr.payslip'].create({'name': 'Private original grid slip', 'number': 'PRIVATE/ORIGINAL/GRID',
            'company_id': self.company.id, 'employee_id': self.contract.employee_id.id, 'contract_id': self.contract.id,
            'struct_id': self.structure.id, 'date_from': fields.Date.today().replace(day=1), 'date_to': fields.Date.today(),
            'credit_note': credit_note})

    def _snapshot(self, slip):
        moves = self.scope['account.move'].search([('journal_id', '=', self.journal.id)])
        return (slip.read(['id', 'state', 'number', 'line_ids', 'move_id', 'compute_date']),
            slip.line_ids.read(['id', 'salary_rule_id', 'amount', 'quantity', 'rate', 'total']),
            moves.read(['id', 'state', 'name', 'line_ids']),
            moves.line_ids.read(['id', 'account_id', 'debit', 'credit', 'tax_tag_ids']))

    def test_original_relation_tables_fields_and_nonstored_line_projection_preserve_pairs(self):
        with Form(self.rule, view='payroll.hr_salary_rule_view_form') as editor:
            editor.debit_tag_ids.clear()
            editor.debit_tag_ids.add(self.tags[2])
            editor.credit_tag_ids.clear()
            editor.credit_tag_ids.add(self.tags[0])
        self.assertEqual(self.rule.debit_tag_ids, self.tags[2])
        self.assertEqual(self.rule.credit_tag_ids, self.tags[0])
        with Form(self.rule, view='payroll.hr_salary_rule_view_form') as editor:
            editor.debit_tag_ids.clear()
            editor.debit_tag_ids.add(self.tags[0])
            editor.credit_tag_ids.clear()
            editor.credit_tag_ids.add(self.tags[1])
        for side in ('debit', 'credit'):
            name = side + '_tag_ids'
            field = self.rule._fields[name]
            self.assertEqual((field.comodel_name, field.relation, field.column1, field.column2),
                ('account.account.tag', 'hr_salary_rule_' + side + '_tag_rel', 'hr_salary_rule_id', 'account_account_tag_id'))
            self.assertTrue(field.store)
            self.assertTrue(field.copy)
            self.assertFalse(field.required)
            self.assertFalse(field.readonly)
            line_field = self.scope['hr.payslip.line']._fields[name]
            self.assertFalse(line_field.store)
            self.assertTrue(line_field.readonly)
            self.assertFalse(line_field.copy)
            self.assertIsNone(line_field.relation)
            self.env.cr.execute('SELECT hr_salary_rule_id,account_account_tag_id FROM ' + field.relation + ' WHERE hr_salary_rule_id=%s', (self.rule.id,))
            self.assertEqual(self.env.cr.fetchall(), [(self.rule.id, self.tags[0 if side == 'debit' else 1].id)])
            self.env.cr.execute("""SELECT c.contype,c.confdeltype FROM pg_constraint c
                WHERE c.conrelid=%s::regclass AND c.contype IN ('f','p','u')""", (field.relation,))
            constraints = self.env.cr.fetchall()
            self.assertEqual(sum(kind == 'f' and deletion == 'c' for kind, deletion in constraints), 2)
            self.assertTrue(any(kind in ('p', 'u') for kind, deletion in constraints))
        slip = self._slip()
        slip.compute_sheet()
        self.assertEqual(slip.line_ids.debit_tag_ids, self.tags[0])
        self.assertEqual(slip.line_ids.credit_tag_ids, self.tags[1])
        self.assertEqual(self.rule._step_original_account_tag_members('debit_tag_ids'), self.tags[0])

    def test_real_oca_posting_preserves_configured_account_sides_signs_and_fiscal_inversion(self):
        for amount, credit_note in ((100, False), (-100, False), (100, True), (-100, True)):
            self.rule.amount_fix = amount
            slip = self._slip(credit_note=credit_note)
            slip.compute_sheet()
            before = slip.line_ids.read(['id', 'salary_rule_id', 'amount', 'quantity', 'rate', 'total'])
            slip.with_context(without_compute_sheet=True).action_payslip_done()
            self.assertFalse(slip.env.su)
            self.assertEqual(slip.state, 'done')
            self.assertEqual(slip.move_id.state, 'posted')
            self.assertEqual(slip.credit_note, credit_note)
            # OCA explicitly negates credit notes. This is its observed source
            # contract; it is not asserted equivalent to native refunds.
            expected = -amount if credit_note else amount
            self.assertEqual(sum(slip.move_id.line_ids.mapped('balance')), 0.0)
            self.assertEqual(sum(slip.move_id.line_ids.mapped('debit')), abs(expected))
            for account, tag, balance in ((self.debit, self.tags[0], expected), (self.credit, self.tags[1], -expected)):
                entry = slip.move_id.line_ids.filtered(lambda line: line.account_id == account)
                self.assertEqual(len(entry), 1)
                self.assertEqual(entry.balance, balance)
                self.assertEqual(entry.tax_tag_ids, tag)
                # Actual official account engine: a general entry with tags
                # but no tax_ids/repartition has no inbound fiscal inversion.
                self.assertFalse(entry.tax_tag_invert)
            self.assertEqual(slip.line_ids.read(['id', 'salary_rule_id', 'amount', 'quantity', 'rate', 'total']), before)

    def test_copy_preserves_complete_visible_pairs_and_rejects_hidden_members_before_defaults(self):
        defaults = {'name': 'Private complete original grid copy', 'code': 'PRIVATE_COMPLETE_GRID_COPY', 'struct_id': False}
        values = self.rule.copy_data(default=defaults)[0]
        self.assertEqual(values['debit_tag_ids'], [Command.set(self.tags[0].ids)])
        self.assertEqual(values['credit_tag_ids'], [Command.set(self.tags[1].ids)])
        copied = self.rule.copy(default=defaults)
        self.assertFalse(copied.env.su)
        self.assertEqual(copied._step_original_account_tag_members('debit_tag_ids'), self.tags[0])
        self.assertEqual(copied._step_original_account_tag_members('credit_tag_ids'), self.tags[1])
        incompatible = self.env['account.account.tag'].create({'name': 'Private visible incompatible copied grid',
            'applicability': 'accounts'}).with_env(self.scope)
        self.rule.write({'debit_tag_ids': [Command.set((self.tags[0] | incompatible).ids)]})
        self.rule.invalidate_recordset(['debit_tag_ids'])
        # The regular domain hides this visible incompatible pair. It must not
        # be silently dropped by Model.copy_data's ordinary M2M getter.
        self.assertEqual(self.rule.debit_tag_ids, self.tags[0])
        source_ids = sorted((self.tags[0] | incompatible).ids)
        values = self.rule.copy_data(default=defaults)[0]
        self.assertEqual(values['debit_tag_ids'], [Command.set(source_ids)])
        copied = self.rule.copy(default=defaults)
        self.assertEqual(sorted(copied._step_original_account_tag_members('debit_tag_ids').ids), source_ids)
        with self.assertRaisesRegex(UserError, 'active tax grids'):
            copied._step_original_account_tags('debit_tag_ids', self.company)
        # An explicit, authorized replacement remains an intentional operation.
        replaced = self.rule.copy(default=dict(defaults, debit_tag_ids=[Command.set(self.tags[2].ids)]))
        self.assertEqual(replaced._step_original_account_tag_members('debit_tag_ids'), self.tags[2])
        self.assertEqual(replaced._step_original_account_tag_members('credit_tag_ids'), self.tags[1])

        def pairs():
            result = {}
            for side in ('debit', 'credit'):
                self.env.cr.execute('SELECT account_account_tag_id FROM hr_salary_rule_' + side
                    + '_tag_rel WHERE hr_salary_rule_id=%s ORDER BY account_account_tag_id', (self.rule.id,))
                result[side] = self.env.cr.fetchall()
            return result

        before_pairs = pairs()
        before_count = self.scope['hr.salary.rule'].search_count([])
        self.assertTrue(incompatible.name)
        hidden = self.env['ir.rule'].create({'name': 'Private hidden original copied grid',
            'model_id': self.env.ref('account.model_account_account_tag').id,
            'domain_force': "[('id','!=',%d)]" % incompatible.id})
        for operation in (lambda: self.rule.copy_data(default=defaults),
                lambda: self.rule.sudo().copy_data(default=dict(defaults, debit_tag_ids=False)),
                lambda: self.rule.copy(default=dict(defaults, debit_tag_ids=[Command.clear()])),
                lambda: self.rule.sudo().copy(default=dict(defaults, debit_tag_ids=[Command.set(self.tags[2].ids)])),
                lambda: self.rule.sudo().with_context(default_debit_tag_ids=[Command.clear()]).copy(default=defaults)):
            with self.assertRaises(AccessError):
                operation()
            self.assertEqual(pairs(), before_pairs)
            self.assertEqual(self.scope['hr.salary.rule'].search_count([]), before_count)
        hidden.unlink()
        # Explicit replacement cannot smuggle a newly hidden target either.
        hidden = self.env['ir.rule'].create({'name': 'Private hidden copied grid replacement',
            'model_id': self.env.ref('account.model_account_account_tag').id,
            'domain_force': "[('id','!=',%d)]" % self.tags[2].id})
        for method in (self.rule.copy_data, self.rule.sudo().copy):
            with self.assertRaises(AccessError):
                method(default=dict(defaults, debit_tag_ids=[Command.set(self.tags[2].ids)]))
        hidden.unlink()
        masters_before = self.env['account.account.tag'].search_count([])
        original_name = self.tags[0].name
        for command in (Command.create({'name': 'Private forbidden copied master', 'applicability': 'taxes'}),
                Command.update(self.tags[0].id, {'name': 'Private forbidden master update'}), Command.delete(self.tags[0].id)):
            with self.assertRaisesRegex(UserError, 'cannot change tag masters'):
                self.rule.sudo().copy(default=dict(defaults, debit_tag_ids=[command]))
            self.assertEqual(pairs(), before_pairs)
            self.assertEqual(self.scope['hr.salary.rule'].search_count([]), before_count)
            self.assertEqual(self.env['account.account.tag'].search_count([]), masters_before)
            self.assertEqual(self.tags[0].name, original_name)

    def test_actual_oca_tax_preparation_unions_existing_provider_grid_without_changing_values(self):
        provider_grid = self.env['account.account.tag'].create({'name': '+Private real OCA base grid',
            'applicability': 'taxes', 'country_id': self.company.country_id.id}).with_env(self.scope)
        group = self.env['account.tax.group'].with_company(self.company).create({'name': 'Private real OCA tax group',
            'company_id': self.company.id, 'country_id': self.company.country_id.id})
        tax = self.env['account.tax'].with_company(self.company).create({'name': 'Private real OCA base tax',
            'company_id': self.company.id, 'country_id': self.company.country_id.id,
            'amount': 0, 'type_tax_use': 'none', 'tax_group_id': group.id,
            'invoice_repartition_line_ids': [Command.create({'repartition_type': 'base', 'tag_ids': [Command.set(provider_grid.ids)]}),
                Command.create({'repartition_type': 'tax', 'account_id': self.debit.id, 'tag_ids': [Command.set(provider_grid.ids)]})],
            'refund_repartition_line_ids': [Command.create({'repartition_type': 'base', 'tag_ids': [Command.set(provider_grid.ids)]}),
                Command.create({'repartition_type': 'tax', 'account_id': self.debit.id, 'tag_ids': [Command.set(provider_grid.ids)]})]})
        child = self.scope['hr.salary.rule'].create({'name': 'Private real OCA tax child', 'code': 'PRIVATE_ORIGINAL_GRID_TAX',
            'sequence': 2, 'company_id': self.company.id, 'category_id': self.rule.category_id.id,
            'struct_id': False, 'tax_base_id': self.rule.id, 'account_tax_id': tax.id,
            'condition_select': 'none', 'amount_select': 'fix', 'amount_fix': 0})
        slip = self._slip()
        slip.compute_sheet()
        line = slip.line_ids.filtered(lambda row: row.salary_rule_id == self.rule)
        self.assertEqual(len(line), 1)
        before = self._snapshot(slip)
        for method, account, tag in ((slip._prepare_debit_line, self.debit, self.tags[0]),
                (slip._prepare_credit_line, self.credit, self.tags[1])):
            result = method(line, 100, slip.date_to, account.id, {})
            self.assertEqual(result['account_id'], account.id)
            self.assertEqual(result['tax_tag_ids'], [Command.set(sorted((provider_grid | tag).ids))])
            self.assertEqual(result['tax_ids'], [(Command.LINK, tax.id, 0)])
            self.assertEqual(result['debit'] + result['credit'], 100.0)
        self.assertEqual(self._snapshot(slip), before)
        # Exercise the other actual LGPL provider branch. Its [] += recordset
        # produces a list of tag records, not ORM commands or a recordset.
        child.tax_base_id = False
        self.rule.account_tax_id = tax.with_env(self.scope)
        for method, account, tag in ((slip._prepare_debit_line, self.debit, self.tags[0]),
                (slip._prepare_credit_line, self.credit, self.tags[1])):
            result = method(line, 100, slip.date_to, account.id, {})
            self.assertEqual(result['tax_tag_ids'], [Command.set(sorted((provider_grid | tag).ids))])
            self.assertFalse(result['tax_ids'])
            self.assertEqual(result['tax_line_id'], tax.id)
            self.assertEqual(result['tax_repartition_line_id'], tax.invoice_repartition_line_ids.filtered(
                lambda row: row.repartition_type == 'tax').id)
            self.assertEqual(result['account_id'], account.id)
            self.assertEqual(result['debit'] + result['credit'], 100.0)
        self.assertEqual(self._snapshot(slip), before)

    def test_hidden_member_blocks_complete_posting_even_with_warm_cache_and_sudo(self):
        self.rule.write({'debit_tag_ids': [Command.set((self.tags[0] | self.tags[2]).ids)]})
        slip = self._slip()
        slip.compute_sheet()
        self.assertEqual(self.rule.debit_tag_ids, self.tags[0] | self.tags[2])
        self.assertTrue(self.tags[2].name)
        before = self._snapshot(slip)
        self.env['ir.rule'].create({'name': 'Private hidden payroll grid contribution',
            'model_id': self.env.ref('account.model_account_account_tag').id,
            'domain_force': "[('id','!=',%d)]" % self.tags[2].id})
        with self.assertRaises(AccessError):
            slip.sudo().with_context(without_compute_sheet=True).action_payslip_done()
        self.assertEqual(self._snapshot(slip), before)

    def test_tag_and_relation_field_permissions_are_checked_before_mutation(self):
        slip = self._slip()
        slip.compute_sheet()
        before = self._snapshot(slip)
        for field in (self.rule._fields['debit_tag_ids'], self.rule._fields['credit_tag_ids'],
                self.tags._fields['country_id'], self.tags._fields['applicability'], self.tags._fields['active'],
                self.scope['account.move.line']._fields['tax_tag_ids']):
            with patch.object(field, 'groups', 'base.group_system'), self.assertRaises(AccessError):
                slip.sudo().with_context(without_compute_sheet=True).action_payslip_done()
            self.assertEqual(self._snapshot(slip), before)

    def test_inactive_wrong_applicability_or_country_are_retained_and_blocked_before_posting(self):
        slip = self._slip()
        slip.compute_sheet()
        before = self._snapshot(slip)
        source = self.tags[0].with_env(self.env)
        for field, value, original in (('active', False, True), ('applicability', 'accounts', 'taxes'),
                ('applicability', 'products', 'taxes'), ('country_id', self.env.ref('base.us').id, self.company.country_id.id)):
            source[field] = value
            with self.assertRaises(UserError):
                slip.with_context(without_compute_sheet=True).action_payslip_done()
            self.assertEqual(source[field].id if field == 'country_id' else source[field], value)
            self.assertEqual(self._snapshot(slip), before)
            source[field] = original
        self.rule.write({'debit_tag_ids': [Command.set(self.tags[2].ids)]})
        slip.with_context(without_compute_sheet=True).action_payslip_done()
        self.assertEqual(slip.move_id.line_ids.filtered(lambda line: line.account_id == self.debit).tax_tag_ids, self.tags[2])

    def test_wrong_company_context_blocks_without_reassigning_rule_tags(self):
        other = self.env['res.company'].create({'name': 'Private wrong grid company', 'country_id': self.company.country_id.id})
        self.scope.user.with_env(self.env).write({'company_ids': [Command.link(other.id)]})
        slip = self._slip()
        slip.compute_sheet()
        before = self._snapshot(slip)
        wrong = slip.with_context(allowed_company_ids=(self.company | other).ids).with_company(other)
        with self.assertRaisesRegex(UserError, 'company context'):
            wrong.with_context(without_compute_sheet=True).action_payslip_done()
        self.assertEqual(self._snapshot(slip), before)
        self.assertEqual(self.rule.debit_tag_ids, self.tags[0])
        self.assertEqual(self.rule.credit_tag_ids, self.tags[1])

    def test_closed_stored_lines_and_posted_grids_do_not_follow_later_master_changes(self):
        slip = self._slip()
        slip.compute_sheet()
        slip.with_context(without_compute_sheet=True).action_payslip_done()
        before = self._snapshot(slip)
        self.rule.write({'debit_tag_ids': [Command.set(self.tags[2].ids)], 'credit_tag_ids': [Command.clear()]})
        self.tags[0].with_env(self.env).active = False
        self.contract.wage = 900000
        with patch.object(type(slip), 'compute_sheet', side_effect=AssertionError('Closed salary cannot be recalculated')):
            self.assertEqual(slip._get_line_values([self.rule.code])[self.rule.code][slip.id]['total'], 100.0)
            self.assertEqual(self._snapshot(slip), before)
        with self.assertRaisesRegex(UserError, 'Closed payroll'):
            slip.with_context(without_compute_sheet=True).action_payslip_done()
        self.assertEqual(self._snapshot(slip), before)
