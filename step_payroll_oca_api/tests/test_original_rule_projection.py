"""Real master projection, complete visibility and no historical payroll writes."""
from unittest import TestCase
from unittest.mock import patch

from psycopg2 import sql

from odoo import api, Command, fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class OriginalRuleProjectionCase(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({'name': 'Private original projection company',
            'country_id': cls.env.ref('base.cl').id, 'currency_id': cls.env.ref('base.CLP').id})
        actor = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Private original projection manager', 'login': 'private-original-projection-manager',
            'company_id': cls.company.id, 'company_ids': [Command.set(cls.company.ids)],
            'groups_id': [Command.set([cls.env.ref(name).id for name in (
                'base.group_user', 'payroll.group_payroll_manager', 'hr.group_hr_manager', 'account.group_account_manager')])]})
        cls.scope = api.Environment(cls.env.cr, actor.id, dict(cls.env.context, allowed_company_ids=cls.company.ids, lang='en_US'), su=False)
        cls.kind = cls.scope['hr.payroll.structure.type'].create({'name': 'Private original projection type'})
        cls.structures = cls.scope['hr.payroll.structure'].create([{
            'name': 'Private original projection ' + name, 'code': 'PRIVATE_PROJECTION_' + name,
            'parent_id': False, 'company_id': cls.company.id, 'type_id': cls.kind.id} for name in ('A', 'B')])
        cls.category = cls.scope['hr.salary.rule.category'].create({'name': 'Private original projection category',
            'code': 'PRIVATE_PROJECTION_CAT', 'company_id': cls.company.id})
        cls.rules = cls.scope['hr.salary.rule'].create([cls._rule_values(index, structure) for index, structure in enumerate(cls.structures)])
        cls.expected = [(structure.id, rule.id) for structure, rule in zip(cls.structures, cls.rules)]

    @classmethod
    def _rule_values(cls, index, structure):
        return {'name': 'Private original projected rule %s' % index, 'code': 'PRIVATE_PROJECTED_%s' % index,
            'category_id': cls.category.id, 'company_id': cls.company.id, 'struct_id': structure.id,
            'condition_select': 'none', 'amount_select': 'fix', 'amount_fix': 100.0}

    def _gap(self, pairs=None):
        # Deliberately incomplete *private fixture* storage mirrors the state
        # between original master adoption and this explicit relation stage.
        self.env.flush_all()
        for structure, rule in pairs if pairs is not None else self.expected:
            self.env.cr.execute('DELETE FROM hr_structure_salary_rule_rel WHERE struct_id=%s AND rule_id=%s', (structure, rule))
        self.structures.invalidate_recordset(['rule_ids'])

    def _stored(self, extra_rules=None):
        self.env.flush_all()
        rules = self.rules | (extra_rules if extra_rules is not None else self.scope['hr.salary.rule'])
        result = {}
        for name, table, ids in (('structures', 'hr_payroll_structure', self.structures.ids), ('rules', 'hr_salary_rule', rules.ids),
                ('categories', 'hr_salary_rule_category', self.category.ids), ('types', 'hr_payroll_structure_type', self.kind.ids)):
            self.env.cr.execute('SELECT to_jsonb(t) FROM ' + table + ' t WHERE id=ANY(%s) ORDER BY id', (ids,))
            result[name] = self.env.cr.fetchall()
        self.env.cr.execute('''SELECT struct_id,rule_id FROM hr_structure_salary_rule_rel
            WHERE struct_id=ANY(%s) OR rule_id=ANY(%s) ORDER BY struct_id,rule_id''', (self.structures.ids, rules.ids))
        result['pairs'] = self.env.cr.fetchall()
        self.env.cr.execute("SELECT md5(coalesce(string_agg(to_jsonb(t)::text,E'\\n' ORDER BY id),'')) FROM ir_sequence t")
        result['sequence_definitions'] = self.env.cr.fetchone()
        self.env.cr.execute("SELECT md5(coalesce(string_agg(to_jsonb(t)::text,E'\\n' ORDER BY id),'')) FROM ir_sequence_date_range t")
        result['sequence_ranges'] = self.env.cr.fetchone()
        self.env.cr.execute("SELECT sequencename FROM pg_sequences WHERE schemaname='public' AND sequencename LIKE 'ir_sequence_%%' ORDER BY sequencename")
        counters = {}
        for (name,) in self.env.cr.fetchall():
            self.env.cr.execute(sql.SQL('SELECT last_value,is_called FROM {}').format(sql.Identifier(name)))
            counters[name] = self.env.cr.fetchone()
        result['postgres_sequence_counters'] = counters
        return result

    def _hide(self, model, domain):
        return self.env['ir.rule'].create({'name': 'Private original projection visibility',
            'model_id': self.env['ir.model']._get_id(model), 'domain_force': repr(domain)})

    def test_71_explicit_real_pairs_are_materialized_once_without_master_or_counter_writes(self):
        extra = self.scope['hr.salary.rule'].create([self._rule_values(index, self.structures[index % 2]) for index in range(2, 71)])
        expected = self.expected + [(self.structures[index % 2].id, rule.id) for index, rule in enumerate(extra, start=2)]
        (self.rules | extra)[::10].active = False
        self._gap(expected)
        before = self._stored(extra)
        result = self.structures._step_materialize_original_rule_projection(expected)
        after = self._stored(extra)
        self.assertEqual(result['created_memberships'], 71)
        self.assertEqual(result['memberships'], 71)
        self.assertEqual(after['pairs'], sorted(expected))
        self.assertEqual({name: value for name, value in before.items() if name != 'pairs'},
            {name: value for name, value in after.items() if name != 'pairs'})
        self.assertEqual(len(self.structures.with_context(active_test=False).rule_ids), 71)
        self.assertEqual(self.structures._step_materialize_original_rule_projection(expected)['created_memberships'], 0)
        self.assertEqual(self._stored(extra), after)
        self.assertFalse(result['master_rows_written'])
        self.assertFalse(result['payroll_read_or_recomputed'])
        self.assertFalse(result['source_identity_certified'])
        self.assertFalse(result['original_metadata_ttype_converted'])

    def test_readonly_admission_and_generic_copy_sharing_remain_distinct(self):
        before = self._stored()
        self.assertTrue(self.structures._step_check_original_rule_projection(self.expected)['projection_equivalent'])
        self.assertEqual(self._stored(), before)
        copied = self.structures[0].copy({'name': 'Private legitimate generic OCA copy'})
        self.assertEqual(copied.rule_ids, self.structures[0].rule_ids)
        before = self._stored()
        for operation in (self.structures._step_check_original_rule_projection, self.structures._step_materialize_original_rule_projection):
            with TestCase.assertRaisesRegex(self, UserError, 'Extra or shared'):
                operation(self.expected)
            self.assertEqual(self._stored(), before)
        self.assertEqual(self.structures._fields['rule_ids'].type, 'many2many')
        for model, name in (('hr.payroll.structure', 'type_id'), ('hr.salary.rule', 'struct_id'),
                ('hr.salary.rule', 'category_id'), ('hr.salary.rule', 'code'), ('hr.salary.rule.category', 'code')):
            self.assertFalse(self.scope[model]._fields[name].required)

    def test_explicit_source_pairs_reject_null_wrong_duplicate_and_incomplete_owners(self):
        before = self._stored()
        wrong = [(self.structures[1].id, self.rules[0].id), self.expected[1]]
        for expected in (wrong, self.expected[:1], self.expected + self.expected[:1], [(False, self.rules[0].id)]):
            with TestCase.assertRaises(self, UserError):
                self.structures._step_materialize_original_rule_projection(expected)
            self.assertEqual(self._stored(), before)
        optional = self.scope['hr.salary.rule'].create({'name': 'Private actual optional OCA rule', 'company_id': self.company.id,
            'struct_id': False, 'category_id': False, 'code': False, 'condition_select': 'none', 'amount_select': 'fix', 'amount_fix': 1})
        generic = self.scope['hr.payroll.structure'].create({'name': 'Private actual optional OCA structure', 'company_id': self.company.id,
            'type_id': False, 'parent_id': False, 'rule_ids': [Command.link(optional.id)]})
        with TestCase.assertRaisesRegex(self, UserError, 'ownership differs'):
            generic._step_materialize_original_rule_projection([(generic.id, optional.id)])
        self.assertFalse(optional.struct_id)
        self.assertIn(optional, generic.rule_ids)

    def test_hidden_physical_rules_structures_and_field_acl_reject_warm_sudo(self):
        self._gap()
        before = self._stored()
        self.rules.sudo().read(['struct_id'])
        hidden = self._hide('hr.salary.rule', [('id', '!=', self.rules[1].id)])
        with TestCase.assertRaises(self, AccessError):
            self.structures.sudo()._step_materialize_original_rule_projection(self.expected)
        self.assertEqual(self._stored(), before)
        hidden.unlink()
        hidden = self._hide('hr.payroll.structure', [('id', '!=', self.structures[1].id)])
        with TestCase.assertRaises(self, AccessError):
            self.structures.sudo()._step_materialize_original_rule_projection(self.expected)
        self.assertEqual(self._stored(), before)
        hidden.unlink()
        for field, operation in ((self.rules._fields['struct_id'], self.structures._step_check_original_rule_projection),
                (self.structures._fields['rule_ids'], self.structures.sudo()._step_materialize_original_rule_projection)):
            with patch.object(field, 'groups', 'base.group_system'):
                with TestCase.assertRaises(self, AccessError):
                    operation(self.expected)
            self.assertEqual(self._stored(), before)

    def test_original_hierarchy_cycles_cannot_be_admitted_or_repaired_by_projection(self):
        self.env.flush_all()
        self.env.cr.execute('UPDATE hr_payroll_structure SET parent_id=%s WHERE id=%s', (self.structures[1].id, self.structures[0].id))
        self.env.cr.execute('UPDATE hr_payroll_structure SET parent_id=%s WHERE id=%s', (self.structures[0].id, self.structures[1].id))
        self.structures.invalidate_recordset(['parent_id'])
        before = self._stored()
        with TestCase.assertRaisesRegex(self, UserError, 'cycle'):
            self.structures._step_materialize_original_rule_projection(self.expected)
        self.assertEqual(self._stored(), before)
        self.env.cr.execute('UPDATE hr_payroll_structure SET parent_id=NULL WHERE id=ANY(%s)', (self.structures.ids,))
        self.structures.invalidate_recordset(['parent_id'])
        self.env.cr.execute('UPDATE hr_salary_rule SET parent_rule_id=%s WHERE id=%s', (self.rules[1].id, self.rules[0].id))
        self.env.cr.execute('UPDATE hr_salary_rule SET parent_rule_id=%s WHERE id=%s', (self.rules[0].id, self.rules[1].id))
        self.rules.invalidate_recordset(['parent_rule_id'])
        before = self._stored()
        with TestCase.assertRaisesRegex(self, UserError, 'cycle'):
            self.structures._step_materialize_original_rule_projection(self.expected)
        self.assertEqual(self._stored(), before)

    def test_real_late_record_denial_rolls_back_pairs_and_membership_cache(self):
        self._gap()
        self._hide('hr.payroll.structure', ['|', ('id', '!=', self.structures[1].id), ('rule_ids', 'not in', self.rules[1].ids)])
        before = self._stored()
        # This is a real record rule that rejects the owner only after its
        # missing pair exists. The assertion supplies no outer savepoint.
        with TestCase.assertRaises(self, AccessError):
            self.structures._step_materialize_original_rule_projection(self.expected)
        self.assertEqual(self._stored(), before)
        self.assertFalse(self.structures.with_context(active_test=False).rule_ids)

    def test_real_projection_consumer_rechecks_required_endpoint_acl_and_rolls_back(self):
        self._gap()
        before = self._stored()
        self.company.with_env(self.scope).sudo().read(['country_id'])
        # The actual materializer inserts the explicit pairs before invoking
        # required admission. A late field/endpoint denial must roll that
        # insertion back without granting configuration access or changing PKs.
        for record, name in ((self.structures, 'type_id'), (self.kind, 'name'),
                (self.category, 'code'), (self.company.with_env(self.scope), 'country_id')):
            with self.subTest(model=record._name, field=name), patch.object(record._fields[name], 'groups', 'base.group_system'):
                with TestCase.assertRaises(self, AccessError):
                    self.structures.sudo()._step_materialize_original_rule_projection(self.expected)
            self.assertEqual(self._stored(), before)
            self.assertFalse(self.structures.with_context(active_test=False).rule_ids)
        hidden = self._hide('hr.payroll.structure.type', [('id', '!=', self.kind.id)])
        with TestCase.assertRaises(self, AccessError):
            self.structures.sudo()._step_materialize_original_rule_projection(self.expected)
        hidden.unlink()
        self.assertEqual(self._stored(), before)
        self.assertEqual(self.structures._step_materialize_original_rule_projection(self.expected)['created_memberships'], 2)
        after = self._stored()
        self.assertEqual({key: value for key, value in before.items() if key != 'pairs'},
            {key: value for key, value in after.items() if key != 'pairs'})
        self.assertEqual(self.structures._step_materialize_original_rule_projection(self.expected)['created_memberships'], 0)
        self.assertEqual(self._stored(), after)

    def test_projection_does_not_read_or_recalculate_real_closed_payroll_or_ledger(self):
        journal = self.scope['account.journal'].create({'name': 'Private projection journal', 'code': 'PRJ', 'type': 'general', 'company_id': self.company.id})
        debit, credit = self.scope['account.account'].create([
            {'name': 'Private projection cost', 'code': '949801', 'account_type': 'expense', 'company_ids': [Command.set(self.company.ids)]},
            {'name': 'Private projection debt', 'code': '949802', 'account_type': 'liability_current', 'company_ids': [Command.set(self.company.ids)]}])
        self.rules[0].write({'account_debit': debit.id, 'account_credit': credit.id})
        author = self.env['hr.contract'].with_company(self.company).env
        employee = author['hr.employee'].create({'name': 'Private closed projection worker', 'company_id': self.company.id})
        values = {'name': 'Private closed projection contract', 'employee_id': employee.id, 'company_id': self.company.id,
            'date_start': fields.Date.today().replace(day=1), 'state': 'open', 'wage': 100, 'schedule_pay': 'monthly',
            'struct_id': self.structures[0].id, 'structure_type_id': self.kind.id, 'journal_id': journal.id}
        if 'contract_type_id' in author['hr.contract']._fields:
            field = author['hr.contract']._fields['contract_type_id']
            values['contract_type_id'] = author[field.comodel_name].search([], limit=1).id
        contract = author['hr.contract'].create(values)
        slip = self.scope['hr.payslip'].create({'name': 'Private closed projection slip', 'number': 'PRIVATE/PROJECTION/CLOSED',
            'employee_id': employee.id, 'company_id': self.company.id, 'contract_id': contract.id,
            'struct_id': self.structures[0].id, 'date_from': values['date_start'], 'date_to': fields.Date.today()})
        slip.compute_sheet()
        slip.with_context(without_compute_sheet=True).action_payslip_done()
        self.assertEqual(slip.state, 'done')
        self.assertEqual(slip.move_id.state, 'posted')
        def history():
            self.env.flush_all()
            result = []
            for table, column, ident in (('hr_payslip', 'id', slip.id), ('hr_payslip_line', 'slip_id', slip.id),
                    ('account_move', 'id', slip.move_id.id), ('account_move_line', 'move_id', slip.move_id.id)):
                self.env.cr.execute('SELECT to_jsonb(t) FROM ' + table + ' t WHERE ' + column + '=%s ORDER BY id', (ident,))
                result.append(self.env.cr.fetchall())
            return result
        self._gap()
        before, masters = history(), self._stored()
        self.company.with_env(self.scope).sudo().read(['country_id'])
        with patch.object(self.company._fields['country_id'], 'groups', 'base.group_system'):
            with TestCase.assertRaises(self, AccessError):
                self.structures.sudo()._step_materialize_original_rule_projection(self.expected)
        self.assertEqual(history(), before)
        self.assertEqual(self._stored(), masters)
        result = self.structures._step_materialize_original_rule_projection(self.expected)
        self.assertEqual(history(), before)
        self.assertEqual(self._stored()['structures'], masters['structures'])
        self.assertEqual(self._stored()['rules'], masters['rules'])
        self.assertFalse(result['payroll_read_or_recomputed'])
