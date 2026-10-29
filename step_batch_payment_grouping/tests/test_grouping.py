from odoo import Command, fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged
from odoo.tests.common import new_test_user
from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged('post_install', '-at_install', 'batch_grouping')
class BatchGroupingCase(AccountTestInvoicingCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Only new, transactional company-specific sequences; never touch source counters.
        sequences = cls.env['ir.sequence'].sudo().with_company(cls.env.company)
        for code in ('account.payment', 'account.outbound.batch.payment', 'account.inbound.batch.payment'):
            if sequences.search_count([('code', '=', code), ('company_id', '=', cls.env.company.id)]):
                raise AssertionError('Grouping fixture company already owns sequence %s' % code)
            private = sequences.create({'name': 'Private grouping fixture ' + code, 'code': code,
                'company_id': cls.env.company.id, 'implementation': 'no_gap',
                'prefix': 'QA/GROUP/', 'padding': 6, 'number_next': 1})
            selected = sequences.search([('code', '=', code), ('company_id', 'in', [False, cls.env.company.id])],
                                        order='company_id', limit=1)
            if selected != private:
                raise AssertionError('Fixture could consume original numbering')

    def setUp(self):
        super().setUp()
        self.env = self.env(context=dict(self.env.context, no_reset_password=True,
            tracking_disable=True, mail_notrack=True, mail_create_nosubscribe=True,
            mail_notify_force_send=False))
        if 'account.batch.payment' not in self.env:
            self.skipTest('Requires a real batch provider; the grouping addon declares none')
        self.actor = new_test_user(self.env, login='batch_grouping_actor',
            groups='account.group_account_invoice,base.group_multi_company',
            company_id=self.env.company.id, company_ids=[Command.set(self.env.company.ids)])
        self.service = self.env['step.batch.payment.grouping'].with_user(self.actor)
        self.journal = self.company_data['default_journal_bank']
        self.first = self.make_payment(100)
        self.second = self.make_payment(250)

    def make_payment(self, amount=100, **extra):
        values = {'payment_type': 'outbound', 'partner_type': 'supplier',
            'partner_id': self.partner_a.id, 'amount': amount,
            'journal_id': self.journal.id, 'date': fields.Date.today(),
            'payment_method_line_id': self.journal.outbound_payment_method_line_ids[:1].id}
        values.update(extra)
        return self.env['account.payment'].create(values)

    def group(self, payments=None):
        payments = self.first | self.second if payments is None else payments
        batch_id = self.service.create_group(payments.ids, 'QA grupo existente')
        return self.env['account.batch.payment'].with_user(self.actor).browse(batch_id)

    def payment_snapshot(self, payments):
        return payments.sudo().read(['name', 'date', 'amount', 'state', 'move_id',
            'currency_id', 'company_id', 'payment_method_line_id', 'is_sent', 'is_matched'])

    def test_real_group_preserves_provider_identity_and_payments(self):
        payments = self.first | self.second
        before = self.payment_snapshot(payments)
        count = self.env['account.payment'].search_count([])
        moves = self.env['account.move'].search_count([])
        method_module = self.env['account.batch.payment'].create.__module__
        batch = self.group()
        self.assertEqual(batch._table, 'account_batch_payment')
        self.assertEqual(batch.state, 'draft')
        self.assertEqual(set(batch.payment_ids.ids), set(payments.ids))
        self.assertEqual(payments.mapped('batch_payment_id'), batch)
        self.assertEqual(self.payment_snapshot(payments), before)
        self.assertEqual(self.env['account.payment'].search_count([]), count)
        self.assertEqual(self.env['account.move'].search_count([]), moves)
        self.assertEqual(self.env['account.batch.payment'].create.__module__, method_module)
        if self.env['ir.module.module'].sudo().search_count([('name', '=', 'account_batch_payment'), ('state', '=', 'installed')]):
            self.assertEqual(method_module, 'odoo.addons.account_batch_payment.models.account_batch_payment')
            self.assertNotIn('step_batch_payment_core', self.env.registry._init_modules)

    def test_replace_membership_keeps_removed_and_added_payment_rows(self):
        third = self.make_payment(75)
        payments = self.first | self.second | third
        before = self.payment_snapshot(payments)
        batch = self.group()
        self.service.replace_group_payments(batch.id, (self.second | third).ids)
        self.assertFalse(self.first.batch_payment_id)
        self.assertEqual(set(batch.payment_ids.ids), set((self.second | third).ids))
        self.assertEqual(self.payment_snapshot(payments), before)

    def test_delete_draft_detaches_without_deleting_or_reposting_payments(self):
        payments = self.first | self.second
        before = self.payment_snapshot(payments)
        batch = self.group()
        self.service.delete_draft_group(batch.id)
        self.assertFalse(batch.exists())
        self.assertEqual(payments.exists(), payments)
        self.assertFalse(payments.mapped('batch_payment_id'))
        self.assertEqual(self.payment_snapshot(payments), before)

    def test_repeated_ids_and_relational_commands_are_rejected(self):
        for ids in ([self.first.id, self.first.id], [Command.create({'amount': 10})], [], [True], [0]):
            with self.assertRaises(UserError):
                self.service.create_group(ids, 'No crear')
        self.assertFalse(self.first.batch_payment_id)

    def test_other_group_membership_cannot_be_stolen(self):
        batch = self.group(self.first)
        with self.assertRaises(UserError):
            self.group()
        self.assertEqual(self.first.batch_payment_id, batch)
        self.assertFalse(self.second.batch_payment_id)

    def test_different_journals_are_rejected(self):
        journal = self.journal.copy({'name': 'Banco aislado segundo', 'code': 'QGR2'})
        second = self.make_payment(journal_id=journal.id,
            payment_method_line_id=journal.outbound_payment_method_line_ids[:1].id)
        with self.assertRaises(UserError):
            self.group(self.first | second)

    def test_different_currency_is_rejected(self):
        currency = self.env.ref('base.EUR') if self.first.currency_id != self.env.ref('base.EUR') else self.env.ref('base.USD')
        currency.active = True
        self.second.currency_id = currency
        with self.assertRaises(UserError):
            self.group()

    def test_different_direction_is_rejected(self):
        self.second.write({'payment_type': 'inbound', 'partner_type': 'customer',
            'payment_method_line_id': self.journal.inbound_payment_method_line_ids[:1].id})
        with self.assertRaises(UserError):
            self.group()

    def test_sent_payment_is_rejected_without_partial_group(self):
        self.second.is_sent = True
        with self.assertRaises(UserError):
            self.group()
        self.assertFalse(self.first.batch_payment_id)

    def test_readonly_actor_cannot_create_replace_or_delete(self):
        batch = self.group()
        readonly = new_test_user(self.env, login='batch_grouping_readonly',
            groups='account.group_account_readonly', company_id=self.env.company.id,
            company_ids=[Command.set(self.env.company.ids)])
        service = self.service.with_user(readonly)
        for method, args in ((service.create_group, (self.first.ids, 'No permitido')),
                             (service.replace_group_payments, (batch.id, self.first.ids)),
                             (service.delete_draft_group, (batch.id,))):
            with self.assertRaises(AccessError):
                method(*args)

    def test_hidden_payment_rejects_whole_create(self):
        self.hide_second()
        with self.assertRaises(AccessError):
            self.group()
        self.assertFalse((self.first | self.second).sudo().mapped('batch_payment_id'))

    def hide_second(self):
        return self.env['ir.rule'].sudo().create({'name': 'Hide grouping fixture payment',
            'model_id': self.env['ir.model']._get_id('account.payment'),
            'domain_force': "[('id', '!=', %s)]" % self.second.id,
            'groups': [Command.link(self.env.ref('account.group_account_invoice').id)]})

    def test_hidden_existing_member_blocks_replace_and_delete(self):
        batch = self.group()
        before = self.payment_snapshot(self.first | self.second)
        self.hide_second()
        for method, args in ((self.service.replace_group_payments, (batch.id, self.first.ids)),
                             (self.service.delete_draft_group, (batch.id,))):
            with self.assertRaises(AccessError):
                method(*args)
        self.assertEqual(self.payment_snapshot(self.first | self.second), before)
        self.assertEqual(set(batch.sudo().payment_ids.ids), set((self.first | self.second).ids))

    def test_company_access_is_checked_before_grouping(self):
        other = self.env['res.company'].sudo().create({'name': 'Grouping forbidden company'})
        self.actor.sudo().write({'company_id': other.id, 'company_ids': [Command.set(other.ids)]})
        with self.assertRaises(AccessError):
            self.service.with_context(allowed_company_ids=other.ids).create_group(self.first.ids, 'No empresa')

    def test_group_date_and_reference_are_explicit_without_sequence_draw(self):
        batch_id = self.service.create_group(self.first.ids, '  Grupo propio  ', '2026-10-29')
        batch = self.env['account.batch.payment'].browse(batch_id)
        self.assertEqual(batch.name, 'Grupo propio')
        self.assertEqual(str(batch.date), '2026-10-29')
