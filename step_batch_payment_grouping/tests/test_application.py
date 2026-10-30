"""Real receivable/payable application, separately from bank reconciliation."""
from unittest.mock import patch

from odoo import Command, fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged
from odoo.tests.common import new_test_user
from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged('post_install', '-at_install', 'batch_invoice_application')
class BatchInvoiceApplicationCase(AccountTestInvoicingCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        for code in ('account.payment', 'account.outbound.batch.payment',
                     'account.inbound.batch.payment', 'picking.batch'):
            sequence_model = cls.env['ir.sequence'].with_company(cls.env.company)
            if sequence_model.search_count([('code', '=', code), ('company_id', '=', cls.env.company.id)]):
                raise AssertionError('Application fixture needs its own unused counters')
            sequence = sequence_model.create({'name': 'Private counterpart application ' + code,
                'code': code, 'company_id': cls.env.company.id, 'implementation': 'no_gap',
                'prefix': 'PRIVATE/APPLY/', 'padding': 6})
            if sequence_model.search([('code', '=', code), ('company_id', 'in', [cls.env.company.id, False])],
                                     order='company_id', limit=1) != sequence:
                raise AssertionError('Application fixture would consume original numbering')

    def setUp(self):
        super().setUp()
        self.env = self.env(context=dict(self.env.context, no_reset_password=True,
            tracking_disable=True, mail_notrack=True, mail_create_nosubscribe=True,
            mail_notify_force_send=False))
        self.actor = new_test_user(self.env, login='private_counterpart_accountant',
            groups='account.group_account_user,base.group_multi_company',
            company_id=self.env.company.id, company_ids=[Command.set(self.env.company.ids)])
        self.service = self.env['step.batch.payment.grouping'].with_user(self.actor)
        self.journal = self.company_data['default_journal_bank']
        self.assertFalse(self.env.company.tax_exigibility)
        self.invoices, self.payments = self._documents('in_invoice')

    def _documents(self, kind):
        scope = self.env['account.move'].with_user(self.actor)
        invoices, payments = scope, self.env['account.payment'].with_user(self.actor)
        outbound = kind == 'in_invoice'
        account = self.company_data['default_account_expense' if outbound else 'default_account_revenue']
        for amount in (100, 250):
            invoice = scope.create({'move_type': kind, 'partner_id': self.partner_a.id,
                'invoice_date': fields.Date.today(), 'date': fields.Date.today(),
                'invoice_line_ids': [Command.create({'name': 'Private saved invoice application',
                    'quantity': 1, 'price_unit': amount, 'account_id': account.id, 'tax_ids': [Command.clear()]})]})
            invoice.action_post()
            method_lines = (self.journal.outbound_payment_method_line_ids if outbound
                            else self.journal.inbound_payment_method_line_ids)
            payment = payments.create({'payment_type': 'outbound' if outbound else 'inbound',
                'partner_type': 'supplier' if outbound else 'customer', 'partner_id': self.partner_a.id,
                'journal_id': self.journal.id, 'company_id': self.env.company.id,
                'date': fields.Date.today(), 'amount': amount,
                'payment_method_line_id': method_lines.filtered(lambda line: line.payment_method_id.code == 'manual')[:1].id,
                'invoice_ids': [Command.set(invoice.ids)]})
            invoices |= invoice; payments |= payment
        return invoices, payments

    def _group(self, payments=None):
        return self.env['account.batch.payment'].with_user(self.actor).browse(
            self.service.create_group((self.payments if payments is None else payments).ids,
                                      'Private counterpart application group'))

    def _payment_snapshot(self, payments=None):
        return (self.payments if payments is None else payments).sudo().read([
            'id', 'name', 'amount', 'date', 'state', 'move_id', 'invoice_ids',
            'batch_payment_id', 'is_sent', 'is_matched', 'is_reconciled'])

    def _invoice_snapshot(self):
        return self.invoices.sudo().read(['id', 'state', 'amount_total', 'amount_residual', 'payment_state'])

    def _assert_real_application(self, batch, invoices, payments, result):
        self.assertEqual(result['invoice_ids'], sorted(invoices.ids))
        self.assertEqual(result['payment_ids'], sorted(payments.ids))
        self.assertEqual(payments.batch_payment_id, batch)
        self.assertEqual(batch.state, 'draft')
        self.assertEqual(invoices.mapped('amount_residual'), [0, 0])
        self.assertTrue(all(payment.is_reconciled and not payment.is_matched and not payment.is_sent for payment in payments))
        self.assertTrue(all(invoice.payment_state == invoice._get_invoice_in_payment_state() for invoice in invoices))
        self.assertTrue(result['partial_reconcile_ids'])
        partials = self.env['account.partial.reconcile'].with_user(self.actor).browse(result['partial_reconcile_ids'])
        partials.check_access('read')
        self.assertEqual(len(partials), 2)
        pending_total = 0
        for payment in payments:
            self.assertEqual(payment.move_id.state, 'posted')
            pending = payment.move_id.line_ids.filtered(lambda line: line.account_id == payment.outstanding_account_id)
            self.assertEqual(len(pending), 1)
            self.assertEqual(abs(pending.amount_residual), payment.amount)
            self.assertFalse(pending.matched_debit_ids | pending.matched_credit_ids)
            self.assertFalse(pending.statement_line_id)
            pending_total += pending.amount_residual
        self.assertEqual(batch.amount, sum(payments.mapped('amount_signed')))
        self.assertEqual(batch.amount_residual, pending_total)
        self.assertEqual(batch.amount_residual_currency, pending_total)
        with self.assertRaises(UserError):
            self.service.post_groups_against_linked_invoices(batch.ids)

    def test_supplier_bills_apply_real_ledger_counterparts_without_bank_match(self):
        batch = self._group()
        amounts = self.payments.read(['id', 'amount', 'date', 'invoice_ids'])
        ledger = self.invoices.line_ids.read(['id', 'balance', 'amount_currency', 'account_id', 'move_id'])
        payment_count = self.env['account.payment'].search_count([])
        mail_count = self.env['mail.mail'].search_count([])
        result = self.service.post_groups_against_linked_invoices(batch.ids)
        self._assert_real_application(batch, self.invoices, self.payments, result)
        self.assertEqual(self.payments.read(list(amounts[0])), amounts)
        self.assertEqual(self.invoices.line_ids.read(list(ledger[0])), ledger)
        self.assertEqual(self.env['account.payment'].search_count([]), payment_count)
        self.assertEqual(self.env['mail.mail'].search_count([]), mail_count)

    def test_customer_invoices_apply_real_inbound_payments(self):
        invoices, payments = self._documents('out_invoice')
        batch = self._group(payments)
        allocations = [[payment.id, payment.invoice_ids.id] for payment in payments]
        result = self.service.post_groups_against_invoices(batch.ids, allocations)
        self._assert_real_application(batch, invoices, payments, result)

    def test_last_amount_mismatch_prevents_first_posting_or_partial_application(self):
        self.payments[-1].amount = 249
        batch = self._group()
        before, invoices = self._payment_snapshot(), self._invoice_snapshot()
        move_count = self.env['account.move'].search_count([])
        with self.assertRaisesRegex(UserError, 'exactamente'):
            self.service.post_groups_against_linked_invoices(batch.ids)
        self.assertEqual(self._payment_snapshot(), before)
        self.assertEqual(self._invoice_snapshot(), invoices)
        self.assertEqual(self.env['account.move'].search_count([]), move_count)

    def test_explicit_allocation_cannot_override_saved_links_or_omit_members(self):
        batch = self._group()
        before = self._payment_snapshot()
        for allocations in ([], [[True, self.invoices[0].id]],
                            [[self.payments[0].id, self.invoices[-1].id]],
                            [[self.payments[0].id, self.invoices[0].id]] * 2):
            with self.assertRaises(UserError):
                self.service.sudo().post_groups_against_invoices(batch.ids, allocations)
        self.assertEqual(self._payment_snapshot(), before)

    def test_hidden_saved_invoice_is_not_silently_filtered_from_warm_sudo_selection(self):
        batch = self._group()
        self.assertEqual(len(self.payments.invoice_ids), 2)
        before = self._payment_snapshot()
        self.env['ir.rule'].create({'name': 'Private hidden saved invoice',
            'model_id': self.env['ir.model']._get_id('account.move'),
            'domain_force': "[('id','!=',%s)]" % self.invoices[-1].id})
        with self.assertRaises(AccessError):
            self.service.sudo().post_groups_against_linked_invoices(batch.ids)
        self.assertEqual(self._payment_snapshot(), before)

    def test_hidden_invoice_child_and_field_acl_are_checked_before_any_posting(self):
        batch = self._group()
        before = self._payment_snapshot()
        hidden = self.invoices[-1].invoice_line_ids[:1]
        rule = self.env['ir.rule'].create({'name': 'Private hidden full invoice child',
            'model_id': self.env['ir.model']._get_id('account.move.line'),
            'domain_force': "[('id','!=',%s)]" % hidden.id})
        with self.assertRaises(AccessError):
            self.service.sudo().post_groups_against_linked_invoices(batch.ids)
        rule.unlink()
        field = self.env['account.move.line']._fields['balance']
        with patch.object(field, 'groups', 'base.group_system'):
            with self.assertRaises(AccessError):
                self.service.sudo().post_groups_against_linked_invoices(batch.ids)
        self.assertEqual(self._payment_snapshot(), before)

    def test_readonly_and_foreign_company_actors_cannot_apply(self):
        batch = self._group()
        before = self._payment_snapshot()
        reader = new_test_user(self.env, login='private_application_reader',
            groups='account.group_account_readonly', company_id=self.env.company.id,
            company_ids=[Command.set(self.env.company.ids)])
        with self.assertRaises(AccessError):
            self.service.with_user(reader).sudo().post_groups_against_linked_invoices(batch.ids)
        other = self.env['res.company'].create({'name': 'Private foreign application company'})
        outsider = new_test_user(self.env, login='private_application_outsider',
            groups='account.group_account_user', company_id=other.id, company_ids=[Command.set(other.ids)])
        with self.assertRaises(AccessError):
            self.service.with_user(outsider).with_context(allowed_company_ids=other.ids).sudo().post_groups_against_linked_invoices(batch.ids)
        self.assertEqual(self._payment_snapshot(), before)

    def test_previously_applied_invoice_and_payment_history_are_not_rewritten(self):
        invoice = self.invoices[0]
        previous = self.payments[0].copy({'invoice_ids': [Command.set(invoice.ids)]})
        previous.action_post()
        lines = previous.move_id.line_ids.filtered(lambda line: line.account_id == previous.destination_account_id)
        (lines | invoice.line_ids.filtered(lambda line: line.account_id == previous.destination_account_id)).reconcile()
        batch = self._group()
        before = self._payment_snapshot(self.payments | previous)
        ledger = previous.move_id.line_ids.read(['id', 'balance', 'amount_currency', 'amount_residual', 'full_reconcile_id'])
        with self.assertRaises(UserError):
            self.service.post_groups_against_linked_invoices(batch.ids)
        self.assertEqual(self._payment_snapshot(self.payments | previous), before)
        self.assertEqual(previous.move_id.line_ids.read(list(ledger[0])), ledger)

    def test_failure_after_real_reconcile_rolls_back_posts_links_and_matching(self):
        batch = self._group()
        before, invoices = self._payment_snapshot(), self._invoice_snapshot()
        count = self.env['account.move'].search_count([])
        partial_count = self.env['account.partial.reconcile'].search_count([])
        real = type(self.env['account.move.line']).reconcile
        def fail_after_real(lines):
            result = real(lines)
            self.assertTrue(lines.matched_debit_ids | lines.matched_credit_ids)
            raise UserError('Private late application provider failure')
        with patch.object(type(self.env['account.move.line']), 'reconcile', fail_after_real):
            with self.assertRaisesRegex(UserError, 'late application'):
                self.service.post_groups_against_linked_invoices(batch.ids)
        self.assertEqual(self._payment_snapshot(), before)
        self.assertEqual(self._invoice_snapshot(), invoices)
        self.assertEqual(self.env['account.move'].search_count([]), count)
        self.assertEqual(self.env['account.partial.reconcile'].search_count([]), partial_count)

    def test_late_internal_note_failure_is_atomic_after_all_real_applications(self):
        batch = self._group()
        before, invoices = self._payment_snapshot(), self._invoice_snapshot()
        real = type(self.service)._log_group_invoice_application
        def fail_after_real(service, current, payments):
            real(service, current, payments)
            raise UserError('Private late application note failure')
        with patch.object(type(self.service), '_log_group_invoice_application', fail_after_real):
            with self.assertRaisesRegex(UserError, 'late application note'):
                self.service.post_groups_against_linked_invoices(batch.ids)
        self.assertEqual(self._payment_snapshot(), before)
        self.assertEqual(self._invoice_snapshot(), invoices)
        self.assertFalse(batch.message_ids.filtered(lambda message: 'Se aplicaron' in str(message.body)))

    def test_cash_basis_and_discontinued_account_are_rejected_without_posting(self):
        # These are masters of the newly created private fixture company only;
        # no original discontinued account is modified or reactivated.
        discontinued = self.env['account.account'].create({'name': 'Private rejected 210233',
            'code': '210233', 'account_type': 'liability_payable', 'reconcile': True,
            'company_ids': [Command.set(self.env.company.ids)]})
        self.payments[0].destination_account_id = discontinued
        batch = self._group()
        before, invoices = self._payment_snapshot(), self._invoice_snapshot()
        self.env.company.tax_exigibility = True
        with self.assertRaisesRegex(UserError, 'base a caja'):
            self.service.post_groups_against_linked_invoices(batch.ids)
        self.env.company.tax_exigibility = False
        with self.assertRaisesRegex(UserError, '210233'):
            self.service.post_groups_against_linked_invoices(batch.ids)
        self.assertEqual(self._payment_snapshot(), before)
        self.assertEqual(self._invoice_snapshot(), invoices)
