from unittest.mock import patch

from odoo import Command, fields
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class BusinessTests(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.reader = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Business restricted reader', 'login': 'business_restricted_reader',
            'company_id': cls.env.company.id, 'company_ids': [Command.set([cls.env.company.id])],
            'groups_id': [Command.set([cls.env.ref('base.group_user').id])],
        })
        cls.assistant = cls.env['step.support.assistant'].with_user(cls.reader)

    def test_no_arbitrary_model_domain_or_invalid_dates(self):
        for app in ('res.users', 'ir.config_parameter', {'model': 'account.move'}, None):
            with self.assertRaises(ValidationError):
                self.assistant.query_business(app)
        for dates in [('2026-13-31', ''), ('2026-09-30', '2026-01-01'), ('yesterday', ''), (['2026-01-01'], '')]:
            with self.assertRaises(ValidationError):
                self.assistant.query_business('asientos', date_from=dates[0], date_to=dates[1])

    @patch('odoo.addons.step_support_assistant.models.assistant.requests.post')
    def test_unsupported_filters_do_not_query_or_call_provider(self, post):
        for question in ('facturas pendientes del cliente secreto', 'ventas de septiembre', 'últimos 5 asientos', 'facturas de Pedro'):
            with patch.object(type(self.assistant), 'query_business') as query:
                result = self.assistant.ask(question)
                self.assertIn('filtros', result['answer'])
                query.assert_not_called()
        post.assert_not_called()

    def test_no_business_write_route(self):
        for question in ('crear asientos', 'borrar facturas', 'validar colaciones'):
            with patch.object(type(self.assistant), 'query_business') as query:
                self.assertIn('controles habituales', self.assistant.ask(question)['answer'])
                query.assert_not_called()

    def test_accounting_permissions_and_balances(self):
        if 'account.move' not in self.env.registry.models:
            self.skipTest('Accounting is optional; install account in the validation database')
        company = self.env.company
        other = self.env['res.company'].create({'name': 'Business other company', 'currency_id': company.currency_id.id})
        manager_group = self.env.ref('account.group_account_manager')
        self.reader.groups_id = [Command.link(manager_group.id)]
        self.reader.company_ids = [Command.set([company.id, other.id])]
        accounts = self.env['account.account'].create([
            {'name': 'Business test debit', 'code': 'ZZ99101', 'account_type': 'asset_current', 'company_ids': [Command.set([company.id])]},
            {'name': 'Business test credit', 'code': 'ZZ99102', 'account_type': 'liability_current', 'company_ids': [Command.set([company.id])]},
        ])
        journal = self.env['account.journal'].create({'name': 'Business security journal', 'code': 'ZZA', 'type': 'general', 'company_id': company.id})
        def move(value, posted):
            result = self.env['account.move'].create({'journal_id': journal.id, 'date': '2026-09-15', 'ref': 'Business fixture',
                'line_ids': [Command.create({'name': 'Fixture', 'account_id': accounts[0].id, 'debit': value}),
                             Command.create({'name': 'Fixture', 'account_id': accounts[1].id, 'credit': value})]})
            if posted:
                result.action_post()
            return result
        posted = move(125, True)
        draft = move(875, False)
        assistant = self.assistant.with_context(allowed_company_ids=[company.id, other.id])
        with patch('odoo.addons.step_support_assistant.models.assistant.requests.post') as post:
            result = assistant.ask('saldo cuenta ZZ99101 hasta 2026-09-30')
            self.assertIn('125', result['records'][0]['cells'][3])
            self.assertNotIn('1,000', result['answer'])
            post.assert_not_called()
        before = assistant.query_business('saldos', reference='ZZ99101', date_to='2026-09-01')
        self.assertIn('0', before['records'][0]['cells'][3])
        net = assistant.query_business('saldos', reference='ZZ99101', date_from='2026-09-01', date_to='2026-09-30')
        self.assertIn('Movimiento neto', net['answer'])
        rows = assistant.query_business('asientos', date_from='2026-09-01', date_to='2026-09-30')['records']
        self.assertIn(posted.id, [row['id'] for row in rows])
        self.assertIn(draft.id, [row['id'] for row in rows])
        # Record rules still apply to aggregates and lists.
        self.env['ir.rule'].create({'name': 'Business test hide debit lines',
            'model_id': self.env['ir.model']._get_id('account.move.line'),
            'domain_force': repr([('account_id', '!=', accounts[0].id)])})
        restricted = assistant.query_business('saldos', reference='ZZ99101', date_to='2026-09-30')
        self.assertIn('0', restricted['records'][0]['cells'][3])
        # Current-company filtering is additional to allowed-company record rules.
        other_journal = self.env['account.journal'].create({'name': 'Business other journal', 'code': 'ZZB', 'type': 'general', 'company_id': other.id})
        other_move = self.env['account.move'].create({'journal_id': other_journal.id, 'date': '2026-09-15'})
        rows = assistant.query_business('asientos', date_from='2026-09-01', date_to='2026-09-30')['records']
        self.assertNotIn(other_move.id, [row['id'] for row in rows])
        self.reader.groups_id = [Command.set([self.env.ref('base.group_user').id])]
        with self.assertRaises(AccessError):
            assistant.query_business('asientos')

