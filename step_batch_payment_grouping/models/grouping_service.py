"""Manage real draft groups through an existing provider, never post a payment.

This service does not declare account.batch.payment. The native acceptance uses
the unmodified native provider; the Community acceptance uses the separate real
provider. Reconciliation and the sent/reconciled workflow remain out of scope.
"""
from odoo import Command, _, api, fields, models
from odoo.exceptions import AccessError, UserError


class BatchPaymentGroupingService(models.AbstractModel):
    _name = 'step.batch.payment.grouping'
    _description = 'Agrupación segura de pagos existentes en borrador'

    @api.model
    def _provider(self):
        if 'account.batch.payment' not in self.env:
            raise UserError(_('No está instalado un proveedor real de lotes de pago.'))
        model = self.env['account.batch.payment']
        if not model._auto or model._table != 'account_batch_payment':
            raise UserError(_('El proveedor de lotes no tiene el almacenamiento compatible.'))
        return model

    @api.model
    def _ids(self, values):
        if not isinstance(values, (list, tuple)) or not values or any(
                type(value) is not int or value <= 0 for value in values):
            raise UserError(_('Seleccione pagos existentes mediante sus IDs.'))
        if len(set(values)) != len(values):
            raise UserError(_('No se puede incluir un pago más de una vez.'))
        return sorted(values)

    @api.model
    def _lock_payments(self, values):
        ids = self._ids(values)
        payments = self.env['account.payment'].browse(ids)
        payments.check_access('read')
        payments.check_access('write')
        validation_fields = ['batch_payment_id', 'state', 'is_sent', 'is_matched',
            'company_id', 'journal_id', 'currency_id', 'payment_type', 'payment_method_id', 'payment_method_line_id']
        payments.flush_recordset(validation_fields)
        # Lock only IDs, after ORM access. No amounts or private values bypass ORM.
        self.env.cr.execute('SELECT id FROM account_payment WHERE id IN %s ORDER BY id FOR UPDATE', [tuple(ids)])
        if [row[0] for row in self.env.cr.fetchall()] != ids:
            raise UserError(_('Uno de los pagos seleccionados ya no existe.'))
        payments.invalidate_recordset(validation_fields)
        payments.check_access('read')
        payments.check_access('write')
        return payments

    @api.model
    def _lock_batch(self, batch_id):
        if type(batch_id) is not int or batch_id <= 0:
            raise UserError(_('Seleccione un lote existente.'))
        batch = self._provider().browse(batch_id)
        batch.check_access('read')
        batch.check_access('write')
        batch.flush_recordset()
        self.env.cr.execute('SELECT id FROM account_batch_payment WHERE id=%s FOR UPDATE', [batch_id])
        if not self.env.cr.fetchone():
            raise UserError(_('El lote ya no existe.'))
        batch.invalidate_recordset()
        batch.check_access('read')
        batch.check_access('write')
        if batch.state != 'draft':
            raise UserError(_('Sólo se pueden modificar grupos en borrador.'))
        return batch

    @api.model
    def _group_payment_ids(self, batch):
        batch.check_access('read')
        self.env['account.payment'].flush_model(['batch_payment_id'])
        # An O2M may hide a subset. Check the complete inverse relation instead.
        self.env.cr.execute('SELECT id FROM account_payment WHERE batch_payment_id=%s ORDER BY id', [batch.id])
        return [row[0] for row in self.env.cr.fetchall()]

    @api.model
    def _group_payments(self, batch):
        ids = self._group_payment_ids(batch)
        return self._lock_payments(ids) if ids else self.env['account.payment']

    @api.model
    def _validate_payments(self, payments, batch=None):
        if not payments:
            raise UserError(_('Un grupo debe contener al menos un pago existente.'))
        for field in ('company_id', 'journal_id', 'currency_id', 'payment_type', 'payment_method_id'):
            values = payments.mapped(field)
            if isinstance(values, list):
                values = set(values)
            if len(values) != 1:
                raise UserError(_('Los pagos deben compartir empresa, diario, moneda, dirección y método.'))
        first = payments[0]
        if first.company_id not in self.env.companies:
            raise AccessError(_('La empresa del pago no está habilitada para este usuario.'))
        first.journal_id.check_access('read')
        if first.journal_id.type != 'bank' or not first.payment_method_id:
            raise UserError(_('El grupo requiere un diario bancario y un método de pago real.'))
        for payment in payments:
            if payment.batch_payment_id and payment.batch_payment_id != batch:
                raise UserError(_('Un pago ya pertenece a otro lote; sepárelo allí primero.'))
            if payment.state in ('canceled', 'cancel', 'rejected') or payment.is_sent or payment.is_matched:
                raise UserError(_('No se pueden reagrupar pagos cancelados, rechazados, enviados o conciliados.'))
        if batch and (batch.journal_id != first.journal_id or batch.batch_type != first.payment_type
                      or (batch.payment_method_id and batch.payment_method_id != first.payment_method_id)):
            raise UserError(_('Los pagos no corresponden al diario, dirección o método del lote.'))
        return first

    @api.model
    def create_group(self, payment_ids, name, date=None):
        """Return the real batch ID. Existing payments keep their identity/state."""
        with self.env.cr.savepoint():
            return self._create_group(payment_ids, name, date)

    @api.model
    def _create_group(self, payment_ids, name, date=None):
        provider = self._provider()
        provider.check_access('create')
        if not isinstance(name, str) or not name.strip() or len(name) > 200:
            raise UserError(_('Indique una referencia de grupo de hasta 200 caracteres.'))
        payments = self._lock_payments(payment_ids)
        first = self._validate_payments(payments)
        values = {
            'name': name.strip(), 'date': fields.Date.to_date(date) if date else fields.Date.context_today(self),
            'batch_type': first.payment_type, 'journal_id': first.journal_id.id,
            'payment_method_id': first.payment_method_id.id, 'payment_ids': [Command.set(payments.ids)],
        }
        batch = provider.create(values)
        batch.check_access('read')
        if batch.state != 'draft' or set(self._group_payments(batch).ids) != set(payments.ids):
            raise UserError(_('El proveedor no conservó el grupo en borrador con todos los pagos.'))
        return batch.id

    @api.model
    def replace_group_payments(self, batch_id, payment_ids):
        """Replace membership atomically; never create/update/delete payment rows."""
        with self.env.cr.savepoint():
            return self._replace_group_payments(batch_id, payment_ids)

    @api.model
    def _replace_group_payments(self, batch_id, payment_ids):
        batch = self._lock_batch(batch_id)
        ids = self._ids(payment_ids)
        original_ids = self._group_payment_ids(batch)
        locked = self._lock_payments(sorted(set(ids + original_ids)))
        original = locked.browse(original_ids)
        payments = locked.browse(ids)
        if original:
            self._validate_payments(original, batch)
        self._validate_payments(payments, batch)
        batch.write({'payment_ids': [Command.set(payments.ids)]})
        if set(self._group_payments(batch).ids) != set(payments.ids):
            raise UserError(_('El proveedor no conservó todos los pagos seleccionados.'))
        original.invalidate_recordset(['batch_payment_id'])
        return True

    @api.model
    def delete_draft_group(self, batch_id):
        """Detach existing payments and delete only the draft group."""
        with self.env.cr.savepoint():
            return self._delete_draft_group(batch_id)

    @api.model
    def _delete_draft_group(self, batch_id):
        batch = self._lock_batch(batch_id)
        batch.check_access('unlink')
        payments = self._group_payments(batch)
        if payments:
            self._validate_payments(payments, batch)
        batch.unlink()
        return True
