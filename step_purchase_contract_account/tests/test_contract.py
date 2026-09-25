from odoo import Command, fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestContractAccounting(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env['res.partner'].create({'name': 'T30 Test Supplier'})
        cls.debit = cls.env['account.account'].create({'name': 'T30 Contract asset', 'code': 'T30D', 'account_type': 'asset_current'})
        cls.credit = cls.env['account.account'].create({'name': 'T30 Provision', 'code': 'T30C', 'account_type': 'liability_current'})
        cls.journal = cls.env['account.journal'].create({'name': 'T30 Test Contracts', 'code': 'T30C', 'type': 'general', 'contract_provision_account_id': cls.credit.id})
        cls.product = cls.env['product.product'].create({'name': 'T30 Advance', 'property_account_expense_id': cls.debit.id})

    def contract(self):
        c = self.env['step.management.purchase.contract'].create({'partner_id': self.partner.id,
            'journal_id': self.journal.id, 'installment_ids': [Command.create({
                'product_id': self.product.id, 'quantity': 15000, 'price_unit': 1.5,
                'date_due': '2026-11-30'})]})
        c.action_confirm()
        c.installment_ids.action_approve()
        return c

    def test_post_is_balanced_idempotent_and_immutable(self):
        c = self.contract()
        c.action_post_contract()
        m = c.installment_ids.move_id
        self.assertEqual(m.state, 'posted')
        self.assertEqual(sum(m.line_ids.mapped('balance')), 0)
        self.assertEqual(m.line_ids.filtered(lambda l: l.account_id == self.debit).debit, 22500)
        self.assertEqual(m.line_ids.partner_id, self.partner)
        c.action_post_contract()
        self.assertEqual(c.installment_ids.move_id, m)
        self.assertEqual(len(c.move_ids), 1)
        with self.assertRaises(UserError):
            c.installment_ids.write({'quantity': 2})
        with self.assertRaises(UserError):
            c.write({'currency_id': c.currency_id.id})

    def test_missing_configuration_does_not_post(self):
        c = self.contract()
        c.journal_id.contract_provision_account_id = False
        with self.assertRaises(UserError):
            c.action_post_contract()
        self.assertFalse(c.move_ids)

    def test_revision_reverses_provision_and_copies_pending(self):
        c = self.contract()
        c.action_post_contract()
        line = c.installment_ids
        original = line.move_id
        result = c.action_revise()
        revised = self.env[c._name].browse(result['res_id'])
        self.assertTrue(c.is_superseded)
        self.assertFalse(line.active)
        self.assertEqual(line.reversal_move_id.state, 'posted')
        self.assertEqual(line.reversal_move_id.reversed_entry_id, original)
        self.assertEqual(revised.amount_total, 22500)
        self.assertFalse(revised.installment_ids.move_id)
        with self.assertRaises(UserError):
            c.action_revise()

    def test_purchase_supplier_mismatch_rejected(self):
        c = self.contract()
        other = self.env['res.partner'].create({'name': 'Other T30 supplier'})
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            self.env['purchase.order'].create({'partner_id': other.id, 'purchase_contract_id': c.id})

    def test_foreign_currency_amounts(self):
        c = self.contract()
        currency = self.env.ref('base.USD')
        if currency == c.company_id.currency_id:
            currency = self.env.ref('base.EUR')
        currency.active = True
        rate = self.env['res.currency.rate'].search([('currency_id', '=', currency.id),
            ('company_id', '=', c.company_id.id), ('name', '=', fields.Date.today())], limit=1)
        if rate:
            rate.rate = 0.5
        else:
            self.env['res.currency.rate'].create({'currency_id': currency.id, 'company_id': c.company_id.id,
                                                 'name': fields.Date.today(), 'rate': 0.5})
        c.currency_id = currency
        c.action_post_contract()
        debit = c.installment_ids.move_id.line_ids.filtered(lambda l: l.debit)
        self.assertEqual(debit.amount_currency, 22500)
        self.assertAlmostEqual(debit.debit, currency._convert(22500, c.company_id.currency_id, c.company_id, c.accounting_date))

    def test_unpaid_contract_cannot_be_closed(self):
        c = self.contract()
        with self.assertRaises(UserError):
            c.action_close()

    def test_cannot_mark_posted_without_move(self):
        c = self.contract()
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            c.installment_ids.state = 'posted'

    def test_payment_reduces_pending_and_retains_paid_installment_on_revision(self):
        c = self.contract()
        c.action_post_contract()
        line = c.installment_ids
        journal = self.env['account.journal'].create({'name': 'T30 Bank', 'code': 'T30B', 'type': 'bank'})
        method = journal.outbound_payment_method_line_ids[:1]
        payment = self.env['account.payment'].create({'partner_id': c.partner_id.id,
            'partner_type': 'supplier', 'payment_type': 'outbound', 'currency_id': c.currency_id.id,
            'amount': 1000, 'journal_id': journal.id, 'payment_method_line_id': method.id,
            'purchase_contract_installment_id': line.id})
        payment.action_post()
        self.assertIn(payment.state, ('in_process', 'paid'))
        self.assertEqual(line.amount_pending, 21500)
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            payment.amount = 30000
        c.action_revise()
        self.assertTrue(line.active)
        self.assertFalse(line.reversal_move_id)
        self.assertEqual(line.amount_pending, 21500)
