from odoo import Command, fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import Form, tagged
from odoo.tests.common import new_test_user
from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged('post_install', '-at_install', 'batch_core')
class BatchCoreCase(AccountTestInvoicingCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        sequences = cls.env['ir.sequence'].sudo().with_company(cls.env.company)
        code = 'account.payment'
        if sequences.search_count([('code', '=', code), ('company_id', '=', cls.env.company.id)]):
            raise AssertionError('Core fixture company has an existing sequence')
        private = sequences.create({'name': 'Private batch core fixture', 'code': code,
            'company_id': cls.env.company.id, 'implementation': 'no_gap',
            'prefix': 'QA/BATCH/', 'padding': 6, 'number_next': 1})
        if sequences.search([('code', '=', code), ('company_id', 'in', [False, cls.env.company.id])],
                            order='company_id', limit=1) != private:
            raise AssertionError('Fixture would consume a business counter')

    def setUp(self):
        super().setUp()
        self.env = self.env(context=dict(self.env.context, no_reset_password=True,
            tracking_disable=True, mail_notrack=True, mail_create_nosubscribe=True,
            mail_notify_force_send=False))
        self.actor = new_test_user(self.env, login='batch_core_actor',
            groups='account.group_account_invoice,base.group_multi_company',
            company_id=self.env.company.id, company_ids=[Command.set(self.env.company.ids)])
        self.Batch = self.env['account.batch.payment'].with_user(self.actor)
        self.journal = self.company_data['default_journal_bank']
        self.payments = self.env['account.payment'].create([{
            'payment_type': 'outbound', 'partner_type': 'supplier', 'partner_id': self.partner_a.id,
            'amount': amount, 'journal_id': self.journal.id, 'date': fields.Date.today(),
            'payment_method_line_id': self.journal.outbound_payment_method_line_ids[:1].id,
        } for amount in (100, 250)])

    def group(self):
        return self.Batch.create({'name': 'Grupo Community real', 'payment_ids': [Command.set(self.payments.ids)]})

    def hide_payment(self):
        return self.env['ir.rule'].sudo().create({'name': 'Core hidden fixture payment',
            'model_id': self.env['ir.model']._get_id('account.payment'),
            'domain_force': "[('id', '!=', %s)]" % self.payments[-1].id,
            'groups': [Command.link(self.env.ref('account.group_account_invoice').id)]})

    def test_real_form_menu_and_explicit_draft_check(self):
        before = self.payments.read(['amount', 'state', 'move_id', 'is_sent', 'is_matched'])
        with Form(self.Batch.with_context(default_payment_ids=[Command.set(self.payments.ids)])) as form:
            form.name = 'Desde el formulario normal'
            self.assertEqual(form.journal_id, self.journal)
        batch = form.record
        self.assertEqual(set(batch.payment_ids.ids), set(self.payments.ids))
        self.assertEqual(batch.state, 'draft')
        self.assertEqual(batch.action_check_group()['tag'], 'display_notification')
        action = self.env.ref('step_batch_payment_core.action_batch_payment_groups')
        self.assertEqual(action.res_model, batch._name)
        self.assertEqual(action.view_mode, 'list,form')
        menu = self.env.ref('step_batch_payment_core.menu_batch_payment_groups')
        self.assertEqual(menu.action, action)
        self.assertEqual(menu.groups_id, self.env.ref('account.group_account_invoice'))
        self.assertIn('pendientes', self.Batch.get_view(
            view_id=self.env.ref('step_batch_payment_core.view_batch_payment_form').id)['arch'])
        self.assertEqual(self.payments.read(list(before[0].keys() - {'id'})), before)

    def test_validation_never_claims_success_or_changes_payments(self):
        batch = self.group()
        before = self.payments.read(['amount', 'state', 'move_id', 'is_sent', 'is_matched'])
        with self.assertRaises(UserError):
            batch.validate_batch_button()
        self.assertEqual(batch.state, 'draft')
        self.assertFalse(batch.file_generation_enabled)
        self.assertFalse(batch.export_file)
        self.assertEqual(self.payments.read(list(before[0].keys() - {'id'})), before)

    def test_direct_relation_cannot_steal_or_cross_scope(self):
        batch = self.group()
        third = self.payments[:1].copy({'batch_payment_id': False, 'amount': 75})
        other = self.Batch.create({'name': 'Segundo', 'payment_ids': [Command.set(third.ids)]})
        with self.assertRaises(UserError):
            self.payments[:1].with_user(self.actor).write({'batch_payment_id': other.id})
        self.assertEqual(self.payments.batch_payment_id, batch)
        third.with_user(self.actor).write({'batch_payment_id': False})
        third.currency_id = self.env.ref('base.EUR') if self.payments.currency_id != self.env.ref('base.EUR') else self.env.ref('base.USD')
        with self.assertRaises(UserError):
            third.with_user(self.actor).write({'batch_payment_id': batch.id})

    def test_direct_relation_requires_write_access_to_batch(self):
        batch = self.group()
        self.env['ir.rule'].sudo().create({'name': 'Deny core batch fixture writes',
            'model_id': self.env['ir.model']._get_id('account.batch.payment'),
            'domain_force': "[('id', '!=', %s)]" % batch.id,
            'groups': [Command.link(self.env.ref('account.group_account_invoice').id)]})
        with self.assertRaises(AccessError):
            self.payments[:1].with_user(self.actor).write({'batch_payment_id': False})

    def test_rpc_commands_and_context_cannot_create_change_or_delete_payments(self):
        count = self.env['account.payment'].search_count([])
        for command in (Command.create({'amount': 1}), Command.update(self.payments[0].id, {'amount': 1}),
                        Command.delete(self.payments[0].id)):
            with self.assertRaises(UserError):
                self.Batch.create({'name': 'No crear', 'payment_ids': [command]})
            with self.assertRaises(UserError):
                self.Batch.with_context(default_payment_ids=[command]).create({'name': 'No contexto'})
        batch = self.group()
        with self.assertRaises(UserError):
            batch.write({'payment_ids': [Command.delete(self.payments[0].id)]})
        self.assertEqual(self.env['account.payment'].search_count([]), count)
        self.assertEqual(self.payments.mapped('amount'), [100, 250])

    def test_payment_creation_cannot_inject_relation_by_values_or_context(self):
        batch = self.group()
        for model, values in ((self.env['account.payment'].with_user(self.actor), {'batch_payment_id': batch.id}),
                              (self.env['account.payment'].with_user(self.actor).with_context(default_batch_payment_id=batch.id), {})):
            with self.assertRaises(UserError):
                model.create(values)

    def test_grouped_payment_accounting_changes_require_detach(self):
        batch = self.group()
        before = self.payments.read(['amount', 'state', 'move_id', 'is_sent', 'is_matched'])
        for values in ({'amount': 2}, {'is_sent': True}, {'state': 'paid'},
                       {'currency_id': self.env.ref('base.EUR').id}, {'batch_payment_id': False, 'amount': 2}):
            with self.assertRaises(UserError):
                self.payments[:1].with_user(self.actor).write(values)
        with self.assertRaises(UserError):
            self.payments[:1].with_user(self.actor).unlink()
        self.assertEqual(self.payments.read(list(before[0].keys() - {'id'})), before)
        batch.unlink()
        self.assertFalse(self.payments.batch_payment_id)

    def test_cached_amount_binary_and_rpc_remain_private_after_payment_hidden(self):
        batch = self.group()
        batch.read(['amount', 'payment_ids', 'export_file'])
        self.hide_payment()
        for callback in (lambda: batch.read(['amount']), lambda: batch.web_read({'amount': {}}),
                lambda: self.Batch.search_read([('id', '=', batch.id)], ['amount']),
                lambda: batch.export_data(['amount']),
                lambda: self.Batch.read_group([('id', '=', batch.id)], ['amount:sum'], []),
                lambda: self.env['ir.binary'].with_user(self.actor)._find_record(
                    res_model=batch._name, res_id=batch.id, field='export_file')):
            with self.assertRaises(AccessError):
                callback()

    def test_original_storage_roles_and_attachment_contract(self):
        self.assertTrue(self.Batch._auto)
        self.assertFalse(self.Batch._transient)
        self.assertEqual(self.Batch._table, 'account_batch_payment')
        self.assertEqual(self.Batch._fields['payment_ids'].inverse_name, 'batch_payment_id')
        field = self.env['account.payment']._fields['batch_payment_id']
        self.assertEqual((field.comodel_name, field.ondelete, field.copy), ('account.batch.payment', 'set null', False))
        self.assertTrue(self.Batch._fields['export_file'].attachment)
        self.assertEqual(self.Batch._fields['amount'].currency_field, 'currency_id')
        self.assertEqual(self.Batch._fields['amount_residual'].currency_field, 'company_currency_id')
        self.assertEqual(self.Batch._fields['amount_residual_currency'].currency_field, 'currency_id')
        rule = self.env.ref('step_batch_payment_core.account_batch_payment_comp_rule')
        self.assertEqual(rule.domain_force, "['|',('journal_id.company_id','=',False),('journal_id.company_id','parent_of', company_ids)]")

    def test_cannot_import_historical_states_amounts_or_files_by_rpc(self):
        for values in ({'state': 'sent'}, {'amount': 1}, {'amount_residual': 1}, {'export_file': 'YQ=='}):
            with self.assertRaises(UserError):
                self.Batch.create(dict(values, name='No importar', payment_ids=[Command.set(self.payments.ids)]))
        batch = self.group()
        for values in ({'state': 'reconciled'}, {'amount': 1}, {'export_file': 'YQ=='}):
            with self.assertRaises(UserError):
                batch.write(values)

    def test_direct_api_cannot_remove_protected_legacy_draft_member(self):
        batch = self.group()
        self.payments.flush_recordset()
        self.env.cr.execute('UPDATE account_payment SET is_sent=TRUE WHERE id=%s', [self.payments[-1].id])
        for callback in (lambda: self.payments[-1].with_user(self.actor).write({'batch_payment_id': False}),
                         lambda: batch.write({'payment_ids': [Command.set(self.payments[:1].ids)]}),
                         lambda: batch.unlink()):
            with self.assertRaises(UserError):
                callback()
        self.assertEqual(set(batch.payment_ids.ids), set(self.payments.ids))

    def test_core_refuses_cold_native_storage_in_preinit(self):
        from ..hooks import require_clean_provider
        # The hook must accept an already installed core, and refuse an existing
        # storage with no installed core owner. No provider or table is removed.
        module = self.env['ir.module.module'].sudo().search([('name', '=', 'step_batch_payment_core')])
        require_clean_provider(self.env)
        with self.assertRaises(UserError), self.env.cr.savepoint():
            module.state = 'uninstalled'
            require_clean_provider(self.env)
