from lxml import etree
from odoo import Command
from odoo.tests import TransactionCase, tagged
from odoo.tests.common import new_test_user
from odoo.exceptions import UserError


@tagged('post_install', '-at_install')
class JournalBranchesCase(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.root = cls.env['res.company'].create({'name': 'QA169 matriz'})
        cls.branch = cls.env['res.company'].create({'name': 'QA169 sucursal', 'parent_id': cls.root.id})
        cls.nested = cls.env['res.company'].create({'name': 'QA169 segunda', 'parent_id': cls.branch.id})
        cls.other = cls.env['res.company'].create({'name': 'QA169 independiente'})
        cls.user = new_test_user(cls.env, login='qa169-accountant', groups='account.group_account_manager,base.group_multi_company',
            company_id=cls.branch.id, company_ids=[Command.set((cls.root | cls.branch | cls.nested | cls.other).ids)])
        cls.journal = cls.env['account.journal'].with_company(cls.root).create({
            'name': 'QA169 diario matriz', 'code': 'Q169', 'type': 'general', 'company_id': cls.root.id})
        cls.debit = cls.env['account.account'].with_company(cls.root).create({
            'name': 'QA169 gasto', 'code': 'QA1691', 'account_type': 'expense', 'company_ids': [Command.set(cls.root.ids)]})
        cls.credit = cls.env['account.account'].with_company(cls.root).create({
            'name': 'QA169 activo', 'code': 'QA1692', 'account_type': 'asset_current', 'company_ids': [Command.set(cls.root.ids)]})

    def test_visibility_native_hierarchy_membership_and_forms(self):
        journal = self.journal.with_user(self.user).with_company(self.branch)
        self.assertEqual(set(journal.step_available_branch_ids.ids), set((self.branch | self.nested).ids))
        for kind, view in [('form', 'account.view_account_journal_form'), ('list', 'account.view_account_journal_tree')]:
            arch = etree.fromstring(journal.get_view(view_id=self.env.ref(view).id, view_type=kind)['arch'])
            self.assertTrue(arch.xpath("//field[@name='step_available_branch_ids']"))
        self.user.company_ids = [Command.set((self.root | self.branch).ids)]
        journal.invalidate_recordset(['step_available_branch_ids'])
        self.assertEqual(journal.step_available_branch_ids, self.branch)

    def test_branch_posts_in_parent_journal_without_changing_ownership(self):
        moves = self.env['account.move'].with_user(self.user).with_company(self.branch)
        entry = moves.create({'company_id': self.branch.id, 'journal_id': self.journal.id,
            'line_ids': [Command.create({'account_id': self.debit.id, 'debit': 20}),
                         Command.create({'account_id': self.credit.id, 'credit': 20})]})
        entry.action_post()
        self.assertEqual(entry.state, 'posted')
        self.assertEqual(entry.company_id, self.branch)
        self.assertEqual(entry.line_ids.company_id, self.branch)
        self.assertEqual(self.journal.company_id, self.root)
        self.assertEqual(entry.journal_id, self.journal)

    def test_unrelated_company_cannot_use_parent_journal(self):
        with self.assertRaises(UserError), self.cr.savepoint():
            self.env['account.move'].with_user(self.user).with_company(self.other).create({
                'company_id': self.other.id, 'journal_id': self.journal.id,
                'line_ids': [Command.create({'account_id': self.debit.id, 'debit': 20}),
                             Command.create({'account_id': self.credit.id, 'credit': 20})]})
