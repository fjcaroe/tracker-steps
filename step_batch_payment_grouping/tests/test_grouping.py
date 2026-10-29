import json
import logging
import os
from pathlib import Path
from unittest.mock import patch

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
        # An RPC can select a method line outside its UI domain. A uniform
        # journal/method code does not make that foreign line compatible.
        second.write({'journal_id': self.journal.id})
        second.flush_recordset()
        self.env.cr.execute('UPDATE account_payment SET payment_method_line_id=%s WHERE id=%s',
            [journal.outbound_payment_method_line_ids[:1].id, second.id])
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
        count = self.env['account.payment'].search_count([])
        service = self.service.with_context(default_name='No usar', default_state='sent',
            default_amount=999, default_export_file='YQ==', default_approved_by_id=self.actor.id,
            default_payment_ids=[Command.create({'amount': 1})])
        batch_id = service.create_group(self.first.ids, '  Grupo propio  ', '2026-10-29')
        batch = self.env['account.batch.payment'].browse(batch_id)
        self.assertEqual(batch.name, 'Grupo propio')
        self.assertEqual(str(batch.date), '2026-10-29')
        self.assertEqual(batch.state, 'draft')
        self.assertFalse(batch.export_file)
        self.assertEqual(batch.amount, -100)
        if 'approved_by_id' in batch._fields:
            self.assertFalse(batch.approved_by_id)
        self.assertEqual(self.env['account.payment'].search_count([]), count)

    def _protected_original(self, column):
        batch = self.group()
        self.payments = self.first | self.second
        self.payments.flush_recordset()
        self.assertFalse(self.second[column])  # deliberately precache the old value
        # Only this private fixture row: emulate a legacy/concurrent change
        # without running the provider's state compute. Its batch remains draft.
        if column == 'is_sent':
            self.env.cr.execute('UPDATE account_payment SET is_sent=TRUE WHERE id=%s', [self.second.id])
        else:
            self.env.cr.execute('UPDATE account_payment SET is_matched=TRUE WHERE id=%s', [self.second.id])
        for method, args in ((self.service.replace_group_payments, (batch.id, self.first.ids)),
                             (self.service.delete_draft_group, (batch.id,))):
            with self.assertRaises(UserError):
                method(*args)
        self.assertEqual(set(batch.sudo().payment_ids.ids), set(self.payments.ids))
        self.assertTrue(batch.exists())

    def test_sent_original_cannot_be_removed_or_deleted_from_legacy_draft(self):
        self._protected_original('is_sent')

    def test_matched_original_cannot_be_removed_or_deleted_from_legacy_draft(self):
        self._protected_original('is_matched')

    def test_create_late_provider_error_rolls_back_real_membership(self):
        count = self.env['account.batch.payment'].search_count([])
        before = self.payment_snapshot(self.first | self.second)
        real = type(self.service)._group_payments

        def fail_after_creation(service, current):
            payments = real(service, current)
            if set(payments.ids) == set((self.first | self.second).ids):
                raise UserError('Late provider check')
            return payments

        with patch.object(type(self.service), '_group_payments', fail_after_creation):
            with self.assertRaises(UserError):
                self.group()
        self.assertEqual(self.env['account.batch.payment'].search_count([]), count)
        self.assertFalse((self.first | self.second).mapped('batch_payment_id'))
        self.assertEqual(self.payment_snapshot(self.first | self.second), before)

    def test_replace_late_provider_error_rolls_back_real_membership(self):
        batch = self.group()
        third = self.make_payment(30)
        before = self.payment_snapshot(self.first | self.second | third)
        real = type(self.service)._group_payments

        def fail_after_replacement(service, current):
            # Core uses this helper during FK writes; let actual mutations run,
            # then fail only the final service postcondition.
            payments = real(service, current)
            if set(payments.ids) == set((self.second | third).ids):
                raise UserError('Late provider check')
            return payments

        with patch.object(type(self.service), '_group_payments', fail_after_replacement):
            with self.assertRaises(UserError):
                self.service.replace_group_payments(batch.id, (self.second | third).ids)
        self.assertEqual(set(batch.payment_ids.ids), set((self.first | self.second).ids))
        self.assertFalse(third.batch_payment_id)
        self.assertEqual(self.payment_snapshot(self.first | self.second | third), before)

    def test_delete_late_provider_error_restores_group_and_links(self):
        batch = self.group()
        before = self.payment_snapshot(self.first | self.second)
        model = type(batch)
        real = model.unlink

        def fail_after_unlink(records):
            real(records)
            raise UserError('Late provider unlink')

        with patch.object(model, 'unlink', fail_after_unlink):
            with self.assertRaises(UserError):
                self.service.delete_draft_group(batch.id)
        self.assertTrue(batch.exists())
        self.assertEqual(set(batch.payment_ids.ids), set((self.first | self.second).ids))
        self.assertEqual(self.payment_snapshot(self.first | self.second), before)

    def test_native_reference_observes_draft_and_posted_amount_contract(self):
        """Observe actual behavior; do not assert an invented monetary formula."""
        if not self.env['ir.module.module'].sudo().search_count([
                ('name', '=', 'account_batch_payment'), ('state', '=', 'installed')]):
            self.skipTest('Native monetary observation requires the untouched native provider')
        result = {'database': self.env.cr.dbname,
                  'provider': self.env['account.batch.payment'].create.__module__,
                  'groups': {}}
        for label, payments in (('draft', self.first | self.second),
                                ('posted', self.make_payment(80) | self.make_payment(120))):
            if label == 'posted':
                payments.action_post()
            before = self.payment_snapshot(payments)
            batch = self.group(payments)
            result['groups'][label] = {
                'batch': batch.read(['state', 'amount', 'amount_residual', 'amount_residual_currency',
                    'currency_id', 'company_currency_id', 'batch_type'])[0],
                'payments': payments.read(['amount', 'amount_signed', 'amount_company_currency_signed',
                    'state', 'move_id', 'currency_id', 'company_currency_id', 'is_sent', 'is_matched']),
            }
            self.assertEqual(self.payment_snapshot(payments), before)
        logging.getLogger(__name__).info('BATCH_NATIVE_REFERENCE %s', json.dumps(result, default=str, sort_keys=True))
        output = os.environ.get('COMMUNITY_BATCH_REFERENCE_OUTPUT')
        if output:
            path = Path(output).resolve()
            if '/opt/steps-validation/' not in str(path) or self.env.cr.dbname.startswith(('CERRO_', 'SyS')):
                raise AssertionError('Reference output must be a private acceptance artifact')
            with path.open('x', encoding='utf-8') as handle:
                json.dump(result, handle, default=str, sort_keys=True, indent=2)
