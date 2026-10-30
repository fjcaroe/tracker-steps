"""Real Community/native ledger operations on new private draft payments only."""
from unittest.mock import patch

from odoo import Command, fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged
from odoo.tests.common import new_test_user
from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged('post_install', '-at_install', 'batch_payment_posting')
class BatchDraftPaymentPostingCase(AccountTestInvoicingCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._private_sequences(cls.env.company)

    @classmethod
    def _private_sequences(cls, company):
        for code in ('account.payment', 'account.outbound.batch.payment',
                     'account.inbound.batch.payment', 'picking.batch'):
            sequences = cls.env['ir.sequence'].with_company(company)
            if sequences.search_count([('code', '=', code), ('company_id', '=', company.id)]):
                raise AssertionError('Posting fixture company already has a private counter')
            sequence = sequences.create({'name': 'Private batch posting ' + code, 'code': code,
                'company_id': company.id, 'implementation': 'no_gap', 'prefix': 'PRIVATE/POST/', 'padding': 6})
            if sequences.search([('code', '=', code), ('company_id', 'in', [company.id, False])],
                                order='company_id', limit=1) != sequence:
                raise AssertionError('Posting fixture must never consume original numbering')

    def setUp(self):
        super().setUp()
        self.env = self.env(context=dict(self.env.context, no_reset_password=True,
            mail_notrack=True, tracking_disable=True, mail_create_nosubscribe=True,
            mail_notify_force_send=False))
        self.actor = new_test_user(self.env, login='batch_draft_posting_accountant',
            groups='account.group_account_user,base.group_multi_company',
            company_id=self.env.company.id, company_ids=[Command.set(self.env.company.ids)])
        self.service = self.env['step.batch.payment.grouping'].with_user(self.actor)
        self.journal = self.company_data['default_journal_bank']
        self.payments = self._payment(100) | self._payment(250)

    def _payment(self, amount, journal=None):
        journal = journal or self.journal
        return self.env['account.payment'].with_company(journal.company_id).create({
            'payment_type': 'outbound', 'partner_type': 'supplier', 'partner_id': self.partner_a.id,
            'amount': amount, 'journal_id': journal.id, 'company_id': journal.company_id.id,
            'date': fields.Date.today(),
            'payment_method_line_id': journal.outbound_payment_method_line_ids.filtered(
                lambda method: method.payment_method_id.code == 'manual')[:1].id,
        })

    def _group(self, payments=None, service=None):
        service = service or self.service
        ids = (payments if payments is not None else self.payments).ids
        return self.env['account.batch.payment'].with_user(service.env.uid).with_context(service.env.context).browse(
            service.create_group(ids, 'Private existing draft posting'))

    def _snapshot(self, payments=None):
        payments = self.payments if payments is None else payments
        return payments.sudo().read(['id', 'name', 'state', 'amount', 'date', 'company_id',
            'currency_id', 'journal_id', 'move_id', 'batch_payment_id', 'is_sent', 'is_matched'])

    def _other_company(self):
        data = self.setup_other_company()
        company = data['company']
        self._private_sequences(company)
        self.actor.company_ids = [Command.link(company.id)]
        self.partner_a.with_company(company).property_account_payable_id = data['default_account_payable']
        return data

    def test_real_ledger_posting_preserves_payment_ids_group_and_amounts_without_sending(self):
        batch = self._group()
        count = self.env['account.payment'].search_count([])
        moves = self.env['account.move'].search_count([])
        mails = self.env['mail.mail'].search_count([])
        result = self.service.post_group_draft_payments(batch.id)
        self.assertEqual(result['batch_ids'], batch.ids)
        self.assertEqual(result['payment_ids'], self.payments.ids)
        self.assertEqual(set(result['move_ids']), set(self.payments.move_id.ids))
        self.assertEqual(self.env['account.payment'].search_count([]), count)
        self.assertEqual(self.env['account.move'].search_count([]), moves + 2)
        self.assertEqual(self.env['mail.mail'].search_count([]), mails)
        self.assertEqual(self.payments.mapped('amount'), [100, 250])
        self.assertEqual(self.payments.mapped('state'), ['in_process', 'in_process'])
        self.assertFalse(any(self.payments.mapped('is_sent')))
        self.assertFalse(any(self.payments.mapped('is_matched')))
        self.assertEqual(self.payments.batch_payment_id, batch)
        self.assertEqual(batch.state, 'draft')
        for payment in self.payments:
            self.assertEqual(payment.move_id.state, 'posted')
            self.assertEqual(payment.move_id.origin_payment_id, payment)
            self.assertAlmostEqual(sum(payment.move_id.line_ids.mapped('balance')), 0)
        self.assertEqual(len(batch.message_ids.filtered(lambda message: 'contablemente' in str(message.body))), 1)

    def test_company_context_follows_group_without_repricing_or_mixing_companies(self):
        batch = self._group()
        other = self._other_company()['company']
        service = self.service.with_context(allowed_company_ids=(self.env.company | other).ids).with_company(other)
        service.post_group_draft_payments(batch.id)
        self.assertEqual(self.payments.move_id.company_id, self.env.company)
        self.assertEqual(self.payments.batch_payment_id, batch)

    def test_two_company_selection_is_rejected_before_first_ledger_mutation(self):
        first = self._group()
        data = self._other_company()
        service = self.service.with_context(allowed_company_ids=(self.env.company | data['company']).ids)
        other_payment = self._payment(60, data['default_journal_bank'])
        second = self._group(other_payment, service)
        before = self._snapshot(self.payments | other_payment)
        with self.assertRaisesRegex(UserError, 'sola empresa'):
            service.post_groups_draft_payments((first | second).ids)
        self.assertEqual(self._snapshot(self.payments | other_payment), before)

    def test_hidden_payment_rejects_complete_warm_sudo_selection_without_partial_post(self):
        batch = self._group()
        self.assertEqual(len(batch.payment_ids), 2)
        before = self._snapshot()
        rule = self.env['ir.rule'].create({'name': 'Private hidden payment posting rule',
            'model_id': self.env['ir.model']._get_id('account.payment'),
            'domain_force': "[('id','!=',%s)]" % self.payments[-1].id,
            'groups': [Command.link(self.env.ref('account.group_account_user').id)]})
        with self.assertRaises(AccessError):
            self.service.sudo().post_group_draft_payments(batch.id)
        self.assertEqual(self._snapshot(), before)
        rule.unlink()
        field = self.payments._fields['amount']
        original_groups = field.groups
        try:
            field.groups = 'base.group_system'
            with self.assertRaises(AccessError):
                self.service.sudo().post_group_draft_payments(batch.id)
        finally:
            field.groups = original_groups
        self.assertEqual(self._snapshot(), before)

    def test_hidden_group_readonly_and_other_company_actors_cannot_post(self):
        batch = self._group()
        before = self._snapshot()
        rule = self.env['ir.rule'].create({'name': 'Private hidden batch posting rule',
            'model_id': self.env['ir.model']._get_id('account.batch.payment'),
            'domain_force': "[('id','!=',%s)]" % batch.id,
            'groups': [Command.link(self.env.ref('account.group_account_user').id)]})
        with self.assertRaises(AccessError):
            self.service.sudo().post_group_draft_payments(batch.id)
        rule.unlink()
        reader = new_test_user(self.env, login='batch_posting_readonly', groups='account.group_account_readonly',
            company_id=self.env.company.id, company_ids=[Command.set(self.env.company.ids)])
        with self.assertRaises(AccessError):
            self.service.with_user(reader).sudo().post_group_draft_payments(batch.id)
        data = self._other_company()
        outsider = new_test_user(self.env, login='batch_posting_foreign', groups='account.group_account_user',
            company_id=data['company'].id, company_ids=[Command.set(data['company'].ids)])
        with self.assertRaises(AccessError):
            self.service.with_user(outsider).with_context(allowed_company_ids=data['company'].ids).sudo().post_group_draft_payments(batch.id)
        self.assertEqual(self._snapshot(), before)

    def test_existing_posted_or_paid_payment_is_not_reposted_or_changed(self):
        for paid in (False, True):
            with self.env.cr.savepoint():
                payment = self._payment(40)
                payment.action_post()
                if paid:
                    payment.action_validate()
                batch = self._group(self.payments[:1] | payment)
                before = self._snapshot(self.payments[:1] | payment)
                ledger = payment.move_id.line_ids.read(['id', 'balance', 'amount_currency', 'amount_residual'])
                with self.assertRaisesRegex(UserError, 'nuevos en borrador'):
                    self.service.post_group_draft_payments(batch.id)
                self.assertEqual(self._snapshot(self.payments[:1] | payment), before)
                self.assertEqual(payment.move_id.line_ids.read(list(ledger[0].keys())), ledger)
                batch.unlink()

    def test_cash_outstanding_configuration_is_rejected_before_relation_changes(self):
        batch = self._group()
        self.payments.payment_method_line_id.payment_account_id = self.journal.default_account_id
        before = self._snapshot()
        with self.assertRaisesRegex(UserError, 'distinta de efectivo'):
            self.service.post_group_draft_payments(batch.id)
        self.assertEqual(self._snapshot(), before)

    def test_real_provider_failure_rolls_back_moves_states_and_membership(self):
        batch = self._group()
        before = self._snapshot()
        move_count = self.env['account.move'].search_count([])
        real = type(self.payments).action_post
        def fail_after_real_post(payments):
            real(payments)
            self.assertTrue(payments.move_id)
            self.assertTrue(all(move.state == 'posted' for move in payments.move_id))
            raise UserError('Private late provider failure')
        with patch.object(type(self.payments), 'action_post', fail_after_real_post):
            with self.assertRaisesRegex(UserError, 'late provider'):
                self.service.post_group_draft_payments(batch.id)
        self.assertEqual(self._snapshot(), before)
        self.assertEqual(self.env['account.move'].search_count([]), move_count)

    def test_late_log_failure_rolls_back_all_groups_after_real_posts(self):
        batch = self._group()
        third = self._payment(70)
        other = self._group(third)
        all_payments = self.payments | third
        before = self._snapshot(all_payments)
        move_count = self.env['account.move'].search_count([])
        real = type(self.service)._log_group_payment_posting
        def fail_after_real_log(service, current, payments):
            real(service, current, payments)
            raise UserError('Private late log failure')
        with patch.object(type(self.service), '_log_group_payment_posting', fail_after_real_log):
            with self.assertRaisesRegex(UserError, 'late log'):
                self.service.post_groups_draft_payments((batch | other).ids)
        self.assertEqual(self._snapshot(all_payments), before)
        self.assertEqual(self.env['account.move'].search_count([]), move_count)
        self.assertFalse((batch | other).message_ids.filtered(lambda message: 'contablemente' in str(message.body)))

    def test_repeated_posting_is_rejected_without_rewriting_posted_entries(self):
        batch = self._group()
        self.service.post_group_draft_payments(batch.id)
        before = self._snapshot()
        lines = self.payments.move_id.line_ids
        ledger = lines.read(['id', 'balance', 'amount_currency', 'amount_residual', 'move_id'])
        with self.assertRaisesRegex(UserError, 'nuevos en borrador'):
            self.service.post_group_draft_payments(batch.id)
        self.assertEqual(self._snapshot(), before)
        self.assertEqual(lines.read(list(ledger[0].keys())), ledger)

    def test_default_context_cannot_import_a_move_or_create_payments(self):
        batch = self._group()
        count = self.env['account.payment'].search_count([])
        self.service.with_context(default_name='INJECTED', default_move_type='out_invoice',
            default_payment_ids=[Command.create({'amount': 1})], default_auto_post='at_date').post_group_draft_payments(batch.id)
        self.assertEqual(self.env['account.payment'].search_count([]), count)
        self.assertTrue(all(move.move_type == 'entry' and move.name != 'INJECTED' and move.auto_post == 'no'
                            for move in self.payments.move_id))

    def test_empty_repeated_and_noninteger_group_ids_do_not_mutate_payments(self):
        batch = self._group()
        before = self._snapshot()
        for ids in ([], [True], [0], [batch.id, batch.id], [Command.create({'name': 'No group'})]):
            with self.assertRaises(UserError):
                self.service.post_groups_draft_payments(ids)
        self.assertEqual(self._snapshot(), before)
