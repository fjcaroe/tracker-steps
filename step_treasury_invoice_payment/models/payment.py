"""Invoice allocations on native payments and native partial reconciliations."""
import math

from odoo import api, fields, models, Command, _
from odoo.exceptions import UserError, ValidationError


class Allocation(models.Model):
    _name = 'step.treasury.payment.invoice'
    _description = 'Factura seleccionada en un pago'
    _check_company_auto = True
    _rec_name = 'invoice_id'

    payment_id = fields.Many2one('account.payment', required=True, ondelete='cascade', index=True)
    company_id = fields.Many2one(related='payment_id.company_id', store=True)
    currency_id = fields.Many2one(related='payment_id.currency_id')
    invoice_id = fields.Many2one('account.move', required=True, check_company=True, ondelete='restrict')
    invoice_currency_id = fields.Many2one(related='invoice_id.currency_id')
    invoice_date = fields.Date(related='invoice_id.invoice_date')
    due_date = fields.Date(related='invoice_id.invoice_date_due')
    residual = fields.Monetary(related='invoice_id.amount_residual', currency_field='invoice_currency_id', string='Saldo factura')
    available_amount = fields.Monetary(compute='_compute_available', string='Saldo en moneda del pago')
    amount = fields.Monetary(required=True, string='Importe a aplicar')
    _sql_constraints = [('payment_invoice_unique', 'unique(payment_id,invoice_id)', 'La factura ya está seleccionada en este pago.')]

    @api.depends('invoice_id.amount_residual', 'payment_id.currency_id', 'payment_id.date')
    def _compute_available(self):
        for row in self:
            row.available_amount = row.invoice_id.currency_id._convert(
                row.invoice_id.amount_residual, row.currency_id, row.company_id,
                row.payment_id.date or fields.Date.context_today(row)) if row.invoice_id and row.currency_id else 0

    def _check_editable(self):
        self.payment_id.check_access('write')
        if any(payment.state != 'draft' for payment in self.payment_id):
            raise UserError(_('Las facturas y sus importes se modifican únicamente en pagos en borrador.'))

    @api.constrains('payment_id', 'invoice_id', 'amount')
    def _check_allocation(self):
        for row in self:
            row._check_invoice()
            if not math.isfinite(row.amount) or row.currency_id.compare_amounts(row.amount, 0) <= 0:
                raise ValidationError(_('El importe de cada factura debe ser positivo.'))

    def _check_invoice(self):
        for row in self:
            invoice, payment = row.invoice_id, row.payment_id
            invoice.check_access('read')
            if (not payment.partner_id or invoice.company_id != payment.company_id
                    or invoice.commercial_partner_id != payment.partner_id.commercial_partner_id
                    or invoice.move_type != payment._step_invoice_type() or invoice.state != 'posted'):
                raise ValidationError(_('Seleccione una factura contabilizada del cliente o proveedor y empresa del pago.'))

    @api.model_create_multi
    def create(self, values):
        payments = self.env['account.payment'].browse([v['payment_id'] for v in values if v.get('payment_id')])
        if any(payment.state != 'draft' for payment in payments):
            raise UserError(_('Agregue facturas únicamente a pagos en borrador.'))
        payments.check_access('write')
        rows = super().create(values)
        rows.payment_id._step_refresh_total()
        return rows

    def write(self, values):
        self._check_editable()
        if 'payment_id' in values:
            raise UserError(_('No se trasladan asignaciones entre pagos.'))
        result = super().write(values)
        self.payment_id._step_refresh_total()
        return result

    def unlink(self):
        self._check_editable()
        payments = self.payment_id
        result = super().unlink()
        payments._step_refresh_total()
        return result


class Payment(models.Model):
    _inherit = 'account.payment'

    step_invoice_allocation_ids = fields.One2many('step.treasury.payment.invoice', 'payment_id', copy=False,
                                                 string='Facturas a pagar o recaudar')
    step_invoice_amount = fields.Monetary(compute='_compute_step_invoice_amount', string='Total aplicado a facturas')

    @api.depends('step_invoice_allocation_ids.amount')
    def _compute_step_invoice_amount(self):
        for payment in self:
            payment.step_invoice_amount = sum(payment.step_invoice_allocation_ids.mapped('amount'))

    def _step_invoice_type(self):
        self.ensure_one()
        return {('inbound', 'customer'): 'out_invoice', ('outbound', 'supplier'): 'in_invoice'}.get(
            (self.payment_type, self.partner_type))

    def _step_invoice_domain(self):
        self.ensure_one()
        return [('state', '=', 'posted'), ('move_type', '=', self._step_invoice_type()),
                ('company_id', '=', self.company_id.id),
                ('commercial_partner_id', '=', self.partner_id.commercial_partner_id.id),
                ('amount_residual', '>', 0)]

    def action_step_select_invoices(self):
        self.ensure_one()
        self.check_access('write')
        if self.state != 'draft' or not self.partner_id or not self._step_invoice_type():
            raise UserError(_('Seleccione el cliente o proveedor en un pago en borrador.'))
        wizard = self.env['step.treasury.payment.invoice.select'].create({'payment_id': self.id})
        return {'type': 'ir.actions.act_window', 'name': _('Seleccionar facturas pendientes'),
                'res_model': wizard._name, 'res_id': wizard.id, 'view_mode': 'form', 'target': 'new'}

    @api.onchange('step_invoice_allocation_ids')
    def _onchange_step_invoice_total(self):
        if self.step_invoice_allocation_ids:
            self.amount = sum(self.step_invoice_allocation_ids.mapped('amount'))

    @api.onchange('partner_id', 'payment_type', 'partner_type', 'company_id', 'currency_id')
    def _onchange_step_invoice_header(self):
        if self.step_invoice_allocation_ids and self._origin:
            changed = any(self[name] != self._origin[name] for name in
                          ('partner_id', 'payment_type', 'partner_type', 'company_id', 'currency_id'))
            if changed:
                self.step_invoice_allocation_ids = [Command.clear()]
                self.amount = 0
                return {'warning': {'title': _('Seleccione nuevamente las facturas'),
                                    'message': _('Cambió el tercero, tipo, empresa o moneda del pago. Seleccione las facturas correspondientes.') }}

    @api.constrains('partner_id', 'payment_type', 'partner_type', 'company_id', 'step_invoice_allocation_ids')
    def _check_step_invoice_header(self):
        self.step_invoice_allocation_ids._check_invoice()

    def _step_refresh_total(self):
        for payment in self:
            payment.write({'amount': sum(payment.step_invoice_allocation_ids.mapped('amount'))})
            if payment.move_id:
                payment._synchronize_to_moves({'step_invoice_allocation_ids'})

    def _step_open_invoice_lines(self, invoice):
        account_type = 'asset_receivable' if self.partner_type == 'customer' else 'liability_payable'
        lines = invoice.line_ids.filtered(lambda line: line.account_id.account_type == account_type and not line.reconciled)
        if len(lines.account_id) != 1:
            raise UserError(_('La factura %s debe tener un saldo pendiente en una única cuenta por cobrar o pagar.') % invoice.display_name)
        return lines

    def _step_validate_allocations(self, lock=False):
        for payment in self.filtered('step_invoice_allocation_ids'):
            payment.check_access('write')
            rows = payment.step_invoice_allocation_ids
            if lock:
                self.env.flush_all()
                self.env.cr.execute('SELECT id FROM account_payment WHERE id=%s FOR UPDATE', [payment.id])
                invoice_ids = sorted(rows.invoice_id.ids)
                self.env.cr.execute('SELECT id FROM account_move WHERE id=ANY(%s) ORDER BY id FOR UPDATE', [invoice_ids])
                self.env.cr.execute('SELECT id FROM account_move_line WHERE move_id=ANY(%s) ORDER BY id FOR UPDATE', [invoice_ids])
                self.env.invalidate_all()
            rows._check_invoice()
            if payment.payment_token_id:
                raise UserError(_('La distribución por facturas requiere un pago sin cobro automático mediante tarjeta guardada.'))
            if not payment.outstanding_account_id:
                raise UserError(_('Configure la cuenta de pagos o cobros pendientes del método de pago para generar el comprobante.'))
            if payment.currency_id.compare_amounts(payment.amount, sum(rows.mapped('amount'))):
                raise UserError(_('El importe del pago debe coincidir con la suma aplicada a sus facturas.'))
            for row in rows:
                if not math.isfinite(row.amount) or row.currency_id.compare_amounts(row.amount, 0) <= 0:
                    raise UserError(_('Indique un importe positivo para cada factura.'))
                if row.currency_id.compare_amounts(row.amount, row.available_amount) > 0:
                    raise UserError(_('El importe de %s supera su saldo pendiente. Actualice la selección.') % row.invoice_id.display_name)
                payment._step_open_invoice_lines(row.invoice_id)

    def _prepare_move_line_default_vals(self, write_off_line_vals=None, force_balance=None):
        values = super()._prepare_move_line_default_vals(write_off_line_vals=write_off_line_vals, force_balance=force_balance)
        if not self.step_invoice_allocation_ids:
            return values
        self._step_validate_allocations()
        if write_off_line_vals or len(values) != 2:
            raise UserError(_('Esta selección requiere distribuir el pago entre facturas sin ajustes ni diferencias adicionales.'))
        liquidity, template = values
        total_balance = template.get('debit', 0) - template.get('credit', 0)
        sign = -1 if self.payment_type == 'inbound' else 1
        rows = self.step_invoice_allocation_ids.sorted('id')
        assigned = 0
        result = [liquidity]
        for index, row in enumerate(rows):
            balance = (total_balance - assigned if index == len(rows) - 1 else self.currency_id._convert(
                sign * row.amount, self.company_id.currency_id, self.company_id, self.date))
            assigned += balance
            invoice_lines = self._step_open_invoice_lines(row.invoice_id)
            result.append(dict(template, name=row.invoice_id.display_name, account_id=invoice_lines.account_id.id,
                               step_treasury_invoice_id=row.invoice_id.id, amount_currency=sign * row.amount,
                               debit=max(balance, 0), credit=max(-balance, 0)))
        return result

    def _generate_journal_entry(self, write_off_line_vals=None, force_balance=None, line_ids=None):
        selected = self.filtered(lambda payment: payment.step_invoice_allocation_ids and not payment.move_id)
        selected._step_validate_allocations(lock=True)
        if selected and line_ids:
            raise UserError(_('El comprobante se genera desde las facturas seleccionadas en el pago.'))
        return super()._generate_journal_entry(write_off_line_vals=write_off_line_vals, force_balance=force_balance, line_ids=line_ids)

    def _synchronize_to_moves(self, changed_fields):
        selected = self.filtered(lambda payment: payment.step_invoice_allocation_ids
                                 or payment.move_id.line_ids.filtered('step_treasury_invoice_id'))
        super(Payment, self - selected)._synchronize_to_moves(changed_fields)
        if not (set(changed_fields) & (set(self._get_trigger_fields_to_synchronize()) | {'step_invoice_allocation_ids'})):
            return
        for payment in selected.filtered('move_id'):
            if payment.move_id.state != 'draft':
                raise UserError(_('Vuelva el pago a borrador antes de cambiar sus importes o facturas.'))
            payment._step_validate_allocations()
            payment.move_id.with_context(skip_invoice_sync=True).write({
                'name': '/',
                'date': payment.date, 'partner_id': payment.partner_id.id, 'currency_id': payment.currency_id.id,
                'partner_bank_id': payment.partner_bank_id.id, 'journal_id': payment.journal_id.id,
                'line_ids': [Command.clear()] + [Command.create(values) for values in payment._prepare_move_line_default_vals()]})

    def _step_reconcile_invoices(self):
        for payment in self.filtered(lambda p: p.step_invoice_allocation_ids and p.move_id.state == 'posted'):
            for row in payment.step_invoice_allocation_ids:
                counterparts = payment.move_id.line_ids.filtered(
                    lambda line: line.step_treasury_invoice_id == row.invoice_id and not line.reconciled)
                if counterparts:
                    invoice_lines = payment._step_open_invoice_lines(row.invoice_id)
                    (counterparts | invoice_lines).reconcile()

    def action_post(self):
        with self.env.cr.savepoint():
            self.filtered(lambda payment: payment.step_invoice_allocation_ids and payment.state == 'draft')._step_validate_allocations(lock=True)
            return super().action_post()

    def action_cancel(self):
        # Payment providers also call this hook with an empty recordset after
        # manual confirmations. There is no accounting document to cancel.
        if not self:
            return True
        return super().action_cancel()

    def write(self, values):
        guarded = set(self._get_trigger_fields_to_synchronize()) | {'step_invoice_allocation_ids'}
        if set(values) & guarded and any(p.step_invoice_allocation_ids and p.state != 'draft' for p in self):
            raise UserError(_('Las facturas y datos financieros se modifican únicamente en pagos en borrador.'))
        with self.env.cr.savepoint():
            if values.get('state') in ('in_process', 'paid') and not values.get('move_id'):
                selected = self.filtered(lambda payment: payment.step_invoice_allocation_ids and payment.state == 'draft')
                selected._step_validate_allocations(lock=True)
                for payment in selected.filtered('move_id'):
                    expected = payment._prepare_move_line_default_vals()
                    def signature(line):
                        return (line.get('account_id'), line.get('step_treasury_invoice_id') or False,
                                line.get('currency_id'), round(line.get('amount_currency', 0), 8),
                                round(line.get('debit', 0) - line.get('credit', 0), 8))
                    adjustments = payment.move_id.line_ids.filtered('is_operational_exchange_adjustment')
                    if any(not payment.company_id.currency_id.is_zero(line.balance) for line in adjustments):
                        raise UserError(_('Revise el ajuste bimoneda antes de confirmar el pago.'))
                    actual = [{'account_id': line.account_id.id, 'step_treasury_invoice_id': line.step_treasury_invoice_id.id,
                               'currency_id': line.currency_id.id, 'amount_currency': line.amount_currency,
                               'debit': line.debit, 'credit': line.credit} for line in payment.move_id.line_ids - adjustments]
                    if sorted(map(signature, expected)) != sorted(map(signature, actual)):
                        raise UserError(_('El comprobante no coincide con la distribución. Vuelva a guardar las facturas antes de confirmar.'))
            result = super().write(values)
            if values.get('state') in ('in_process', 'paid'):
                self._step_reconcile_invoices()
            return result


class MoveLine(models.Model):
    _inherit = 'account.move.line'

    step_treasury_invoice_id = fields.Many2one('account.move', string='Factura aplicada en Tesorería',
                                              readonly=True, copy=False, check_company=True, ondelete='restrict')


class InvoiceSelection(models.TransientModel):
    _name = 'step.treasury.payment.invoice.select'
    _description = 'Seleccionar facturas pendientes para un pago'

    payment_id = fields.Many2one('account.payment', required=True, readonly=True)
    available_invoice_ids = fields.Many2many('account.move', compute='_compute_available')
    invoice_ids = fields.Many2many('account.move', relation='step_treasury_invoice_select_rel', string='Facturas pendientes')

    @api.depends('payment_id', 'payment_id.partner_id', 'payment_id.payment_type', 'payment_id.partner_type')
    def _compute_available(self):
        for wizard in self:
            wizard.available_invoice_ids = self.env['account.move'].search(wizard.payment_id._step_invoice_domain())

    def action_apply(self):
        self.ensure_one()
        payment = self.payment_id
        payment.check_access('write')
        if payment.state != 'draft' or not payment.partner_id or not payment._step_invoice_type():
            raise UserError(_('Seleccione facturas para un pago en borrador del cliente o proveedor.'))
        if not self.invoice_ids or self.invoice_ids - self.available_invoice_ids:
            raise UserError(_('Seleccione facturas contabilizadas y pendientes del tercero y empresa del pago.'))
        existing = payment.step_invoice_allocation_ids.invoice_id
        values = []
        for invoice in self.invoice_ids - existing:
            amount = invoice.currency_id._convert(invoice.amount_residual, payment.currency_id, payment.company_id, payment.date)
            values.append({'payment_id': payment.id, 'invoice_id': invoice.id, 'amount': amount})
        if values:
            self.env['step.treasury.payment.invoice'].create(values)
        return {'type': 'ir.actions.act_window_close'}
