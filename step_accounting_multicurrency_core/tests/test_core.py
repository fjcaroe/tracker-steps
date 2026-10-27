from datetime import timedelta

from odoo import Command, fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase, Form, tagged
from ..hooks import CORE, LEGACY, VIEWS, FIELDS, alias, adopt_legacy_records, preserve_legacy_xmlids


@tagged('post_install', '-at_install')
class CommunityCurrencyCase(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True, mail_notrack=True,
            no_reset_password=True, mail_create_nosubscribe=True, mail_notify_force_send=False))
        cls.company = cls.env.company
        cls.day = fields.Date.context_today(cls.company)
        cls.operational = cls.env['res.currency'].create({'name': 'XOC', 'symbol': 'OC', 'rounding': 0.01})
        cls.rate = cls.env['res.currency.rate'].create({'name': cls.day, 'currency_id': cls.operational.id,
            'company_id': cls.company.id, 'rate': 1 / 976.82})
        cls.company.operational_currency_id = cls.operational
        def account(code, kind, reconcile=False):
            return cls.env['account.account'].create({'name': 'Community '+code, 'code': code,
                'account_type': kind, 'reconcile': reconcile, 'company_ids': [Command.set(cls.company.ids)]})
        cls.debit = account('QCM1', 'expense')
        cls.credit = account('QCM2', 'liability_payable', True)
        cls.receivable = account('QCM3', 'asset_receivable', True)
        cls.income = account('QCM4', 'income')
        cls.cash = account('QCM5', 'asset_cash', True)
        cls.receipt = account('QCM6', 'asset_current', True)
        cls.company.income_currency_exchange_account_id = cls.income
        cls.company.expense_currency_exchange_account_id = cls.debit
        cls.journal = cls.env['account.journal'].create({'name': 'Community currency', 'code': 'QCM',
            'type': 'general', 'company_id': cls.company.id})
        cls.bank = cls.env['account.journal'].create({'name': 'Community bank', 'code': 'QCMB',
            'type': 'bank', 'company_id': cls.company.id, 'default_account_id': cls.cash.id})
        cls.method = cls.bank.inbound_payment_method_line_ids.filtered(lambda method: method.code == 'manual')[:1]
        cls.method.payment_account_id = cls.receipt
        cls.partner = cls.env['res.partner'].create({'name': 'Community test partner'})
        cls.partner.with_company(cls.company).write({'property_account_receivable_id': cls.receivable.id,
                                                     'property_account_payable_id': cls.credit.id})

    def move(self, split=False, operational=False):
        currency = self.operational if operational else self.company.currency_id
        amounts = (300, -100, -200) if split else (100, -100)
        values = []
        for index, amount in enumerate(amounts):
            balance = currency._convert(amount, self.company.currency_id, self.company, self.day)
            values.append(Command.create({'name': 'Community transaction', 'account_id': (self.debit if index == 0 else self.credit).id,
                'partner_id': self.partner.id, 'currency_id': currency.id, 'amount_currency': amount,
                'debit': max(balance, 0), 'credit': max(-balance, 0)}))
        return self.env['account.move'].create({'journal_id': self.journal.id, 'date': self.day, 'line_ids': values})

    def test_primary_and_operational_books_are_balanced(self):
        move = self.move(); move.action_post()
        self.assertEqual(move.state, 'posted')
        self.assertTrue(self.company.currency_id.is_zero(sum(move.line_ids.mapped('balance'))))
        self.assertTrue(self.operational.is_zero(sum(move.line_ids.mapped('operational_balance'))))
        self.assertAlmostEqual(move.observed_exchange_rate, 976.82, places=2)

    def test_foreign_transaction_uses_its_original_amount_currency(self):
        move = self.move(operational=True); move.action_post()
        for line in move.line_ids.filtered(lambda line: not line.is_operational_exchange_adjustment):
            self.assertEqual(line.operational_balance, line.amount_currency)

    def test_operational_rounding_adds_zero_primary_balance_adjustment(self):
        move = self.move(split=True); move.action_post()
        adjustments = move.line_ids.filtered('is_operational_exchange_adjustment')
        self.assertEqual(len(adjustments), 1)
        self.assertTrue(self.company.currency_id.is_zero(adjustments.balance))
        self.assertTrue(self.operational.is_zero(sum(move.line_ids.mapped('operational_balance'))))
        self.assertEqual(move.line_ids.filtered(lambda line: not line.is_operational_exchange_adjustment).mapped('balance'), [300, -100, -200])

    def test_rate_changes_do_not_rewrite_historical_operational_values(self):
        move = self.move(); move.action_post()
        before = [(line.id, line.operational_exchange_rate, line.operational_balance) for line in move.line_ids]
        self.rate.rate = 1 / 1200
        self.env.invalidate_all()
        self.assertEqual([(line.id, line.operational_exchange_rate, line.operational_balance) for line in move.line_ids], before)

    def test_payment_conversion_uses_payment_date(self):
        payment = self.env['account.payment'].create({'partner_id': self.partner.id, 'partner_type': 'customer',
            'payment_type': 'inbound', 'amount': 976.82, 'date': self.day, 'journal_id': self.bank.id,
            'payment_method_line_id': self.method.id, 'currency_id': self.company.currency_id.id})
        self.assertEqual(payment.operational_currency_id, self.operational)
        self.assertAlmostEqual(payment.conversion_amount, 1, places=2)
        Form(payment, view='account.view_account_payment_form')

    def test_company_rejects_same_primary_and_operational_currency(self):
        with self.assertRaises(ValidationError):
            self.company.operational_currency_id = self.company.currency_id

    def test_native_forms_include_community_currency_fields(self):
        self.env.user.groups_id |= self.env.ref('account.group_account_user') | self.env.ref('base.group_multi_currency')
        move = self.move()
        Form(move, view='account.view_move_form')
        arch = self.env['account.move'].get_view(view_id=self.env.ref('account.view_move_form').id, view_type='form')['arch']
        self.assertIn('operational_exchange_rate', arch)
        settings = self.env['res.config.settings'].get_view(view_id=self.env.ref('account.res_config_settings_view_form').id, view_type='form')['arch']
        self.assertIn('operational_currency_id', settings)

    def test_legacy_and_core_xmlids_reference_the_same_records(self):
        names = list(VIEWS) + ['field_%s__%s' % (model.replace('.', '_'), name) for model, fields_ in FIELDS.items() for name in fields_]
        for name in names:
            self.assertEqual(self.env.ref(CORE+'.'+name), self.env.ref(LEGACY+'.'+name))

    def test_metadata_adoption_is_idempotent(self):
        before = {(record.module, record.name): (record.model, record.res_id) for record in self.env['ir.model.data'].search([
            ('module', 'in', [CORE, LEGACY])])}
        adopt_legacy_records(self.env); preserve_legacy_xmlids(self.env)
        after = {(record.module, record.name): (record.model, record.res_id) for record in self.env['ir.model.data'].search([
            ('module', 'in', [CORE, LEGACY])])}
        self.assertEqual(before, after)

    def test_conflicting_alias_is_rejected(self):
        source = self.env['ir.model.data'].search([('module', '=', CORE), ('name', '=', VIEWS[0])])
        namespace = 'step_core_alias_conflict_test'
        self.env['ir.model.data'].create({'module': namespace, 'name': source.name,
            'model': 'ir.ui.view', 'res_id': self.env.ref('base.view_users_form').id})
        with self.assertRaises(UserError): alias(self.env, source, namespace, True)

    def test_retiring_an_alias_namespace_keeps_core_fields_views_and_values(self):
        namespace = 'step_core_alias_retirement_test'
        names = [VIEWS[0], 'field_res_company__operational_currency_id']
        records = self.env['ir.model.data'].search([('module', '=', CORE), ('name', 'in', names)])
        self.assertEqual(len(records), 2)
        for record in records: alias(self.env, record, namespace, True)
        field = self.env['res.company']._fields['operational_currency_id']
        prefetch = field.prefetch
        try:
            self.env['ir.model.data']._module_data_uninstall([namespace])
        finally:
            # Native uninstall rebuilds the registry afterward; TransactionCase does not.
            field.prefetch = prefetch
            self.env['res.company']._add_field('operational_currency_id', field)
        for name in names: self.assertTrue(self.env.ref(CORE+'.'+name).exists())
        self.assertEqual(self.company.operational_currency_id, self.operational)
