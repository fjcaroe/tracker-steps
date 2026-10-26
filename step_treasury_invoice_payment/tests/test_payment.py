from odoo import Command
from odoo.tests import TransactionCase, Form, tagged
from odoo.tests.common import new_test_user
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools import mute_logger
from .common import fixture, invoice, payment


@tagged('post_install', '-at_install')
class InvoicePaymentCase(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True, mail_notrack=True,
                                      no_reset_password=True, mail_create_nosubscribe=True, mail_notify_force_send=False))
        cls.data = fixture(cls.env)

    def test_customer_two_invoices_have_separate_credit_lines_and_native_reconciliation(self):
        invoices = invoice(self.env, self.data, 100) | invoice(self.env, self.data, 200)
        pay = payment(self.env, self.data, invoices)
        pay.action_post()
        self.assertEqual(pay.move_id.state, 'posted')
        applied = pay.move_id.line_ids.filtered('step_treasury_invoice_id')
        self.assertEqual(len(applied), 2)
        self.assertEqual(applied.step_treasury_invoice_id, invoices)
        self.assertEqual(sorted(applied.mapped('credit')), [100, 200])
        ordinary = pay.move_id.line_ids.filtered(lambda line: not line.is_operational_exchange_adjustment)
        self.assertEqual(len(ordinary), 3)
        self.assertTrue(self.env.company.currency_id.is_zero(sum(pay.move_id.line_ids.mapped('balance'))))
        if pay.move_id.operational_currency_id:
            self.assertTrue(pay.move_id.operational_currency_id.is_zero(sum(pay.move_id.line_ids.mapped('operational_balance'))))
        self.assertEqual(invoices.mapped('amount_residual'), [0, 0])
        self.assertTrue(all(applied.mapped('reconciled')))

    def test_supplier_partial_and_full_invoices_have_separate_debit_lines(self):
        bills = invoice(self.env, self.data, 100, kind='in_invoice') | invoice(self.env, self.data, 200, kind='in_invoice')
        pay = payment(self.env, self.data, bills, [40, 200], supplier=True)
        pay.action_post()
        self.assertEqual(pay.amount, 240)
        self.assertEqual(bills.mapped('amount_residual'), [60, 0])
        self.assertEqual(sorted(pay.move_id.line_ids.filtered('step_treasury_invoice_id').mapped('debit')), [40, 200])

    def test_later_payment_uses_only_remaining_invoice_balance(self):
        inv = invoice(self.env, self.data, 100)
        first = payment(self.env, self.data, inv, [35]); first.action_post()
        self.assertEqual(inv.amount_residual, 65)
        second = payment(self.env, self.data, inv, [65]); second.action_post()
        self.assertEqual(inv.amount_residual, 0)
        self.assertEqual(len(first.move_id.line_ids.filtered('step_treasury_invoice_id')), 1)

    def test_one_invoice_with_several_due_dates_still_has_one_payment_counterpart(self):
        term = self.env['account.payment.term'].create({'name': 'QA123 dos vencimientos',
            'line_ids': [Command.create({'value': 'percent', 'value_amount': 40, 'nb_days': 0}),
                         Command.create({'value': 'percent', 'value_amount': 60, 'nb_days': 30})]})
        inv = invoice(self.env, self.data, 100, term=term)
        self.assertEqual(len(inv.line_ids.filtered(lambda line: line.account_id == self.data['receivable'])), 2)
        pay = payment(self.env, self.data, inv, [50]); pay.action_post()
        self.assertEqual(inv.amount_residual, 50)
        self.assertEqual(len(pay.move_id.line_ids.filtered('step_treasury_invoice_id')), 1)

    def test_foreign_invoice_can_be_paid_in_company_currency(self):
        foreign = self.env['res.currency'].create({'name': 'XIP', 'symbol': 'IP', 'rounding': 0.01})
        self.env['res.currency.rate'].create({'currency_id': foreign.id, 'company_id': self.env.company.id,
            'name': self.data['date'], 'rate': 2})
        inv = invoice(self.env, self.data, 100, currency=foreign)
        amount = foreign._convert(100, self.env.company.currency_id, self.env.company, self.data['date'])
        pay = payment(self.env, self.data, inv, [amount]); pay.action_post()
        self.assertTrue(foreign.is_zero(inv.amount_residual))
        self.assertEqual(pay.move_id.line_ids.filtered('step_treasury_invoice_id').currency_id, self.env.company.currency_id)

    def test_currency_rounding_keeps_split_entry_balanced(self):
        foreign = self.env['res.currency'].create({'name': 'XIR', 'symbol': 'IR', 'rounding': 0.01})
        self.env['res.currency.rate'].create({'currency_id': foreign.id, 'company_id': self.env.company.id,
            'name': self.data['date'], 'rate': 3})
        invoices = self.env['account.move']
        for amount in (100, 101, 103): invoices |= invoice(self.env, self.data, amount, currency=foreign)
        pay = payment(self.env, self.data, invoices, [100, 101, 103], currency=foreign); pay.action_post()
        self.assertTrue(self.env.company.currency_id.is_zero(sum(pay.move_id.line_ids.mapped('balance'))))
        self.assertEqual(len(pay.move_id.line_ids.filtered('step_treasury_invoice_id')), 3)

    def test_wizard_filters_partner_company_posted_type_and_pending_balance(self):
        good = invoice(self.env, self.data)
        wrong_partner = self.env['res.partner'].create({'name': 'QA123 otro tercero'})
        other = invoice(self.env, self.data, partner=wrong_partner)
        draft = invoice(self.env, self.data, post=False)
        bill = invoice(self.env, self.data, kind='in_invoice')
        paid = invoice(self.env, self.data); payment(self.env, self.data, paid).action_post()
        pay = payment(self.env, self.data)
        wizard = self.env['step.treasury.payment.invoice.select'].browse(pay.action_step_select_invoices()['res_id'])
        self.assertIn(good, wizard.available_invoice_ids)
        self.assertFalse((other | draft | bill | paid) & wizard.available_invoice_ids)
        wizard.invoice_ids = good; wizard.action_apply()
        self.assertEqual(pay.amount, 100)
        wizard.action_apply()
        self.assertEqual(len(pay.step_invoice_allocation_ids), 1)

    def test_wizard_rejects_invoice_supplied_outside_its_domain(self):
        bill = invoice(self.env, self.data, kind='in_invoice')
        pay = payment(self.env, self.data)
        wizard = self.env['step.treasury.payment.invoice.select'].create({'payment_id': pay.id, 'invoice_ids': [Command.set(bill.ids)]})
        with self.assertRaises(UserError): wizard.action_apply()

    def test_overpayment_fails_without_creating_a_journal_or_changing_invoice(self):
        inv = invoice(self.env, self.data)
        pay = payment(self.env, self.data, inv, [101])
        with self.assertRaises(UserError): pay.action_post()
        self.assertFalse(pay.move_id)
        self.assertEqual(pay.state, 'draft')
        self.assertEqual(inv.amount_residual, 100)

    def test_stale_selection_is_rechecked_against_native_residual_before_posting(self):
        inv = invoice(self.env, self.data)
        stale = payment(self.env, self.data, inv)
        payment(self.env, self.data, inv, [40]).action_post()
        with self.assertRaises(UserError): stale.action_post()
        self.assertFalse(stale.move_id)
        self.assertEqual(inv.amount_residual, 60)

    def test_amount_must_match_allocation_total(self):
        inv = invoice(self.env, self.data)
        pay = payment(self.env, self.data, inv)
        pay.amount = 99
        with self.assertRaises(UserError): pay.action_post()

    def test_native_payment_without_selection_keeps_standard_journal_and_no_invoice_link(self):
        inv = invoice(self.env, self.data)
        pay = payment(self.env, self.data)
        pay.amount = 30; pay.action_post()
        self.assertEqual(len(pay.move_id.line_ids), 2)
        self.assertFalse(pay.move_id.line_ids.filtered('step_treasury_invoice_id'))
        self.assertEqual(inv.amount_residual, 100)

    def test_posting_twice_is_idempotent(self):
        inv = invoice(self.env, self.data)
        pay = payment(self.env, self.data, inv); pay.action_post()
        lines = pay.move_id.line_ids
        pay.action_post()
        self.assertEqual(pay.move_id.line_ids, lines)
        self.assertEqual(inv.amount_residual, 0)

    def test_posted_allocations_cannot_be_edited_removed_or_appended(self):
        inv = invoice(self.env, self.data)
        pay = payment(self.env, self.data, inv); pay.action_post()
        with self.assertRaises(UserError): pay.step_invoice_allocation_ids.amount = 90
        with self.assertRaises(UserError): pay.step_invoice_allocation_ids.unlink()
        with self.assertRaises(UserError): pay.write({'amount': 90})
        extra = invoice(self.env, self.data)
        with self.assertRaises(UserError):
            self.env['step.treasury.payment.invoice'].create({'payment_id': pay.id, 'invoice_id': extra.id, 'amount': 10})

    def test_return_to_draft_restores_invoice_balance_and_allows_new_partial_amount(self):
        inv = invoice(self.env, self.data)
        pay = payment(self.env, self.data, inv); pay.action_post(); pay.action_draft()
        self.assertEqual(inv.amount_residual, 100)
        pay.step_invoice_allocation_ids.amount = 40
        pay.action_post()
        self.assertEqual(inv.amount_residual, 60)
        self.assertEqual(len(pay.move_id.line_ids), 2)

    def test_copy_does_not_duplicate_invoice_allocation(self):
        inv = invoice(self.env, self.data)
        pay = payment(self.env, self.data, inv)
        self.assertFalse(pay.copy().step_invoice_allocation_ids)

    def test_invoice_cannot_be_duplicated_or_assigned_to_wrong_partner(self):
        inv = invoice(self.env, self.data)
        pay = payment(self.env, self.data, inv)
        with self.assertRaises(Exception), mute_logger('odoo.sql_db'):
            self.env['step.treasury.payment.invoice'].create({'payment_id': pay.id, 'invoice_id': inv.id, 'amount': 1})
        wrong = self.env['res.partner'].create({'name': 'QA123 otro cliente'})
        with self.assertRaises(ValidationError): pay.partner_id = wrong

    def test_native_payment_and_selection_forms_open(self):
        pay = payment(self.env, self.data)
        Form(pay, view='account.view_account_payment_form')
        wizard = self.env['step.treasury.payment.invoice.select'].browse(pay.action_step_select_invoices()['res_id'])
        Form(wizard, view='step_treasury_invoice_payment.invoice_selection_form')

    def test_accounting_user_can_select_and_pay_without_system_administration(self):
        user = new_test_user(self.env, login='qa123-accountant', groups='base.group_user,account.group_account_user',
                             company_id=self.env.company.id, company_ids=[Command.set(self.env.company.ids)])
        inv = invoice(self.env, self.data)
        pay = payment(self.env, self.data, inv).with_user(user)
        self.assertFalse(user.has_group('base.group_system'))
        pay.action_post()
        self.assertEqual(inv.amount_residual, 0)
        Form(pay, view='account.view_account_payment_form')

    def test_user_without_accounting_cannot_create_invoice_allocations(self):
        user = new_test_user(self.env, login='qa123-reader', groups='base.group_user')
        inv = invoice(self.env, self.data)
        pay = payment(self.env, self.data)
        with self.assertRaises(AccessError):
            self.env['step.treasury.payment.invoice'].with_user(user).create({'payment_id': pay.id, 'invoice_id': inv.id, 'amount': 10})

    def test_invoice_allocation_respects_company_access_and_cannot_cross_companies(self):
        other = self.env['res.company'].create({'name': 'QA123 empresa separada', 'currency_id': self.env.company.currency_id.id})
        other_env = self.env['account.payment'].with_company(other).env
        other_data = fixture(other_env, prefix='Q124')
        foreign_invoice = invoice(other_env, other_data)
        foreign_payment = payment(other_env, other_data, foreign_invoice)
        user = new_test_user(self.env, login='qa123-company-user', groups='base.group_user,account.group_account_user',
                             company_id=self.env.company.id, company_ids=[Command.set(self.env.company.ids)])
        with self.assertRaises(AccessError):
            foreign_payment.step_invoice_allocation_ids.with_user(user).with_context(
                allowed_company_ids=self.env.company.ids).read(['amount'])
        local = payment(self.env, self.data)
        with self.assertRaises(UserError):
            self.env['step.treasury.payment.invoice'].create({'payment_id': local.id,
                'invoice_id': foreign_invoice.id, 'amount': 10})
