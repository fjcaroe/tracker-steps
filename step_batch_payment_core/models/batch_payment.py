"""Independent implementation from the metadata contract and Community account API.

Only existing-payment grouping is accepted. No native code is imported, no
native class is replaced, no validated history is recalculated on adoption.
"""
import json

from odoo import Command, _, api, fields, models
from odoo.exceptions import UserError


class AccountBatchPayment(models.Model):
    _name = 'account.batch.payment'
    _description = 'Batch Payment'
    _table = 'account_batch_payment'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'

    @classmethod
    def _build_model(cls, pool, cr):
        if cls._name in pool:
            raise TypeError('step_batch_payment_core refuses to replace an existing account.batch.payment provider')
        return super()._build_model(pool, cr)

    name = fields.Char(required=True, copy=False)
    date = fields.Date(required=True, default=fields.Date.context_today, copy=False)
    state = fields.Selection([('draft', 'New'), ('sent', 'Sent'), ('reconciled', 'Reconciled')],
        compute='_compute_state', store=True, copy=False, readonly=True, compute_sudo=False)
    journal_id = fields.Many2one('account.journal', ondelete='set null')
    company_id = fields.Many2one('res.company', related='journal_id.company_id', compute_sudo=False)
    payment_ids = fields.One2many('account.payment', 'batch_payment_id', required=True, copy=False)
    payment_ids_domain = fields.Char(compute='_compute_payment_ids_domain')
    currency_id = fields.Many2one('res.currency', compute='_compute_currency', store=True,
        copy=False, compute_sudo=False, ondelete='set null')
    company_currency_id = fields.Many2one('res.currency', related='journal_id.company_id.currency_id',
        store=True, compute_sudo=False)
    amount = fields.Monetary(compute='_compute_from_payment_ids', store=True, currency_field='currency_id',
        copy=False, compute_sudo=False)
    amount_residual = fields.Monetary(compute='_compute_from_payment_ids', store=True,
        currency_field='company_currency_id', copy=False, compute_sudo=False)
    amount_residual_currency = fields.Monetary(compute='_compute_from_payment_ids', store=True,
        currency_field='currency_id', copy=False, compute_sudo=False)
    batch_type = fields.Selection([('inbound', 'Inbound'), ('outbound', 'Outbound')], required=True)
    payment_method_id = fields.Many2one('account.payment.method', compute='_compute_payment_method_id',
        store=True, readonly=False, copy=True, compute_sudo=False, ondelete='set null')
    available_payment_method_ids = fields.Many2many('account.payment.method', compute='_compute_available_payment_method_ids')
    payment_method_code = fields.Char(related='payment_method_id.code')
    export_file_create_date = fields.Date(readonly=True, copy=False)
    export_file = fields.Binary(readonly=True, copy=False, attachment=True)
    export_filename = fields.Char(copy=False)
    file_generation_enabled = fields.Boolean(compute='_compute_file_generation_enabled')

    @api.depends('payment_ids.is_sent', 'payment_ids.is_matched')
    def _compute_state(self):
        for batch in self:
            # This provider cannot issue, mark sent or reconcile. Never pretend
            # that one of those operations succeeded from an empty recordset.
            if batch.payment_ids.filtered(lambda payment: payment.is_sent or payment.is_matched):
                raise UserError(_('Este proveedor sólo gestiona grupos no enviados y no conciliados.'))
            batch.state = 'draft'

    @api.depends('payment_ids.currency_id', 'journal_id.currency_id', 'journal_id.company_id.currency_id')
    def _compute_currency(self):
        for batch in self:
            currencies = batch.payment_ids.currency_id
            if len(currencies) > 1:
                raise UserError(_('Un grupo en borrador debe utilizar una sola moneda.'))
            batch.currency_id = currencies or batch.journal_id.currency_id or batch.company_currency_id

    @api.depends('payment_ids.amount', 'payment_ids.payment_type', 'payment_ids.move_id.line_ids.amount_residual',
                 'payment_ids.move_id.line_ids.amount_residual_currency', 'payment_ids.outstanding_account_id')
    def _compute_from_payment_ids(self):
        for batch in self:
            payments = batch._complete_payments()
            batch.amount = sum(payments.mapped('amount_signed'))
            # The accounting lines carry the actual historical exchange rate.
            # Never convert a residual using today's rate or write a payment.
            lines = self.env['account.move.line']
            for payment in payments:
                lines |= payment.move_id.line_ids.filtered(
                    lambda line: line.account_id == payment.outstanding_account_id)
            batch.amount_residual = sum(lines.mapped('amount_residual'))
            batch.amount_residual_currency = sum(lines.mapped('amount_residual_currency'))

    @api.depends('payment_ids.payment_method_id')
    def _compute_payment_method_id(self):
        for batch in self:
            methods = batch.payment_ids.payment_method_id
            if len(methods) > 1:
                raise UserError(_('El grupo debe utilizar un solo método de pago.'))
            batch.payment_method_id = methods

    @api.depends('journal_id', 'batch_type')
    def _compute_available_payment_method_ids(self):
        for batch in self:
            lines = (batch.journal_id.inbound_payment_method_line_ids if batch.batch_type == 'inbound'
                     else batch.journal_id.outbound_payment_method_line_ids)
            batch.available_payment_method_ids = lines.payment_method_id

    @api.depends('journal_id', 'batch_type', 'payment_method_id')
    def _compute_payment_ids_domain(self):
        for batch in self:
            batch.payment_ids_domain = json.dumps([
                ('journal_id', '=', batch.journal_id.id), ('payment_type', '=', batch.batch_type),
                ('payment_method_id', '=', batch.payment_method_id.id), ('batch_payment_id', 'in', [False, batch.id or False])])

    def _compute_file_generation_enabled(self):
        for batch in self:
            batch.file_generation_enabled = False

    def _complete_payments(self):
        self.ensure_one()
        self.check_access('read')
        if not isinstance(self.id, int):
            payments = self.payment_ids
        else:
            self.env['account.payment'].flush_model(['batch_payment_id'])
            self.env.cr.execute('SELECT id FROM account_payment WHERE batch_payment_id=%s ORDER BY id', [self.id])
            payments = self.env['account.payment'].browse([row[0] for row in self.env.cr.fetchall()])
        payments.check_access('read')
        return payments

    def check_access(self, operation):
        result = super().check_access(operation)
        ids = [value for value in self.ids if type(value) is int]
        if ids and operation in ('read', 'write', 'unlink'):
            self.env.cr.execute('SELECT id FROM account_payment WHERE batch_payment_id=ANY(%s)', [ids])
            self.env['account.payment'].browse([row[0] for row in self.env.cr.fetchall()]).check_access('read')
        return result

    def read(self, fields=None, load='_classic_read'):
        self.check_access('read')
        return super().read(fields=fields, load=load)

    def _read_format(self, fnames, load='_classic_read'):
        self.check_access('read')
        return super()._read_format(fnames, load=load)

    def web_read(self, specification):
        self.check_access('read')
        return super().web_read(specification)

    def export_data(self, fields_to_export):
        self.check_access('read')
        return super().export_data(fields_to_export)

    @api.model
    def read_group(self, domain, fields, groupby, offset=0, limit=None, orderby=False, lazy=True):
        self.search(domain).check_access('read')
        return super().read_group(domain, fields, groupby, offset=offset, limit=limit, orderby=orderby, lazy=lazy)

    @api.model
    def _selected_ids(self, commands, initial=()):
        ids = set(initial)
        for command in commands or ():
            if not isinstance(command, (tuple, list)) or not command or command[0] not in (
                    Command.LINK, Command.UNLINK, Command.CLEAR, Command.SET):
                raise UserError(_('Seleccione pagos existentes; el grupo no crea, cambia ni elimina pagos.'))
            if command[0] == Command.SET:
                ids = set(self.env['step.batch.payment.grouping']._existing_payment_ids(command[2]))
            elif command[0] == Command.LINK:
                self.env['step.batch.payment.grouping']._existing_payment_ids([command[1]])
                ids.add(command[1])
            elif command[0] == Command.UNLINK:
                ids.discard(command[1])
            else:
                ids.clear()
        return sorted(ids)

    @api.model
    def default_get(self, fields_list):
        self._selected_ids(self.env.context.get('default_payment_ids', []))
        values = super().default_get(fields_list)
        ids = self._selected_ids(values.get('payment_ids', []))
        if ids:
            payments = self.env['account.payment'].browse(ids)
            payments.check_access('read')
            first = self.env['step.batch.payment.grouping']._validate_payments(payments)
            for field, actual in (('journal_id', first.journal_id.id), ('batch_type', first.payment_type),
                                  ('payment_method_id', first.payment_method_id.id)):
                if field in fields_list:
                    values[field] = actual
        return values

    @api.model_create_multi
    def create(self, values_list):
        with self.env.cr.savepoint():
            return self._create_existing_payment_groups(values_list)

    def _create_existing_payment_groups(self, values_list):
        self.check_access('create')
        self._selected_ids(self.env.context.get('default_payment_ids', []))
        service = self.env['step.batch.payment.grouping']
        prepared = []
        for values in values_list:
            values = dict(values)
            if {'state', 'amount', 'amount_residual', 'amount_residual_currency', 'export_file',
                    'export_file_create_date', 'export_filename', 'currency_id', 'company_currency_id'} & values.keys():
                raise UserError(_('El proveedor calcula los importes; no importa estados o archivos históricos por RPC.'))
            ids = self._selected_ids(values.get('payment_ids', self.env.context.get('default_payment_ids', [])))
            payments = service._lock_payments(ids)
            first = service._validate_payments(payments)
            for field, actual in (('journal_id', first.journal_id.id), ('batch_type', first.payment_type),
                                  ('payment_method_id', first.payment_method_id.id)):
                if values.get(field) and values[field] != actual:
                    raise UserError(_('La cabecera debe corresponder a los pagos seleccionados.'))
                values[field] = actual
            if not isinstance(values.get('name'), str) or not values['name'].strip():
                raise UserError(_('Indique una referencia explícita del grupo.'))
            values['payment_ids'] = [Command.set(ids)]
            prepared.append(values)
        return super().create(prepared)

    def write(self, values):
        with self.env.cr.savepoint():
            return self._write_draft_payment_groups(values)

    def _write_draft_payment_groups(self, values):
        self.check_access('write')
        if set(values) - {'name', 'date', 'payment_ids'}:
            raise UserError(_('En esta etapa sólo se edita la referencia, fecha y selección de un grupo en borrador.'))
        service = self.env['step.batch.payment.grouping']
        for batch in self:
            service._lock_batch(batch.id)
            original = service._group_payment_ids(batch)
            ids = batch._selected_ids(values.get('payment_ids', []), original)
            locked = service._lock_payments(sorted(set(original + ids)))
            if original:
                service._validate_payments(locked.browse(original), batch)
            service._validate_payments(locked.browse(ids), batch)
        return super().write(values)

    def unlink(self):
        with self.env.cr.savepoint():
            return self._unlink_draft_payment_groups()

    def _unlink_draft_payment_groups(self):
        service = self.env['step.batch.payment.grouping']
        for batch in self:
            service._lock_batch(batch.id)
            original = service._group_payments(batch)
            if original:
                service._validate_payments(original, batch)
        self.check_access('unlink')
        return super().unlink()

    def action_check_group(self):
        self.ensure_one()
        self.env['step.batch.payment.grouping']._validate_payments(self._complete_payments(), self)
        return {'type': 'ir.actions.client', 'tag': 'display_notification', 'params': {
            'type': 'info', 'message': _('Grupo en borrador coherente. No se envió, validó ni concilió ningún pago.'),
            'sticky': False}}

    def validate_batch_button(self):
        self.check_access('write')
        raise UserError(_('La validación, envío y conciliación del lote siguen pendientes de certificar en Community.'))
