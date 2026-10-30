"""Post new draft payments through account's real ledger API, not bank validation."""
import math

from odoo import _, api, models
from odoo.exceptions import AccessError, UserError


BATCH_FIELDS = ['name', 'state', 'payment_ids', 'journal_id', 'company_id',
                'currency_id', 'batch_type', 'payment_method_id']
PAYMENT_FIELDS = ['state', 'move_id', 'amount', 'currency_id', 'company_id',
    'journal_id', 'payment_type', 'partner_type', 'partner_id', 'partner_bank_id',
    'payment_method_id', 'payment_method_line_id', 'outstanding_account_id',
    'batch_payment_id', 'is_sent', 'is_matched']
OPTIONAL_FIELDS = ('payment_transaction_id', 'payment_token_id',
                   'paired_internal_transfer_payment_id', 'is_internal_transfer')


class BatchPaymentPostingService(models.AbstractModel):
    _inherit = 'step.batch.payment.grouping'

    @api.model
    def post_group_draft_payments(self, batch_id):
        return self.post_groups_draft_payments([batch_id])

    @api.model
    def post_groups_draft_payments(self, batch_ids):
        """Atomically post existing drafts; retain IDs/membership and draft batch.

        This is not validate_batch_button, a bank transmission or reconciliation.
        No public context flag grants permission or bypasses the relation guard.
        """
        normal = self.sudo(False).with_context({key: value for key, value in self.env.context.items()
                                               if not key.startswith('default_')})
        with normal.env.cr.savepoint():
            return normal._post_groups_draft_payments(batch_ids)

    @api.model
    def _post_groups_draft_payments(self, batch_ids):
        if (not isinstance(batch_ids, (list, tuple)) or not batch_ids
                or any(type(ident) is not int or ident <= 0 for ident in batch_ids)
                or len(set(batch_ids)) != len(batch_ids)):
            raise UserError(_('Seleccione grupos existentes sin repetir sus identificadores.'))
        batches = self._provider().browse(sorted(batch_ids))
        batches.check_access('read')
        batches.check_access('write')
        batches.check_field_access_rights('read', BATCH_FIELDS)
        payment_model = self.env['account.payment']
        extra = [name for name in OPTIONAL_FIELDS if name in payment_model._fields]
        payment_model.check_field_access_rights('read', PAYMENT_FIELDS + extra)
        self.env['account.move'].check_access('create')
        self.env['account.move.line'].check_access('create')
        for batch in batches:
            self._lock_batch(batch.id)
        selections = {batch.id: self._group_payment_ids(batch) for batch in batches}
        if any(not ids for ids in selections.values()):
            raise UserError(_('Todos los grupos deben contener pagos nuevos en borrador.'))
        ids = sorted({ident for selected in selections.values() for ident in selected})
        if len(ids) != sum(map(len, selections.values())):
            raise UserError(_('Un pago no puede pertenecer a varios grupos.'))
        payments = self._lock_payments(ids)
        payments.check_field_access_rights('read', PAYMENT_FIELDS + extra)
        payments.flush_recordset(PAYMENT_FIELDS + extra)
        payments.invalidate_recordset(PAYMENT_FIELDS + extra)
        payments.check_access('read')
        payments.check_access('write')
        for batch in batches:
            self._validate_payments(payments.browse(selections[batch.id]), batch)
        if len(payments.company_id) != 1:
            raise UserError(_('Publique grupos de una sola empresa por operación.'))
        company = payments.company_id
        if company not in self.env.companies:
            raise AccessError(_('La empresa de los pagos no está habilitada en la sesión.'))
        payments = payments.with_company(company)
        batches = batches.with_company(company)
        for payment in payments:
            if payment.state != 'draft' or payment.move_id or payment.is_sent or payment.is_matched:
                raise UserError(_('Sólo se publican pagos nuevos en borrador, sin asiento, envío ni conciliación previos.'))
            if any(payment[name] for name in extra):
                raise UserError(_('Las transacciones de proveedores e iniciativas de transferencia interna requieren su flujo propio.'))
            payment.payment_method_id.check_access('read')
            payment.payment_method_id.check_field_access_rights('read', ['code'])
            if payment.payment_method_id.code != 'manual':
                raise UserError(_('Esta operación sólo publica pagos de método manual; no ejecuta proveedores bancarios.'))
            outstanding = payment.outstanding_account_id
            outstanding.check_access('read')
            outstanding.check_field_access_rights('read', ['account_type', 'deprecated'])
            if not outstanding or outstanding.deprecated or outstanding.account_type == 'asset_cash':
                raise UserError(_('Configure una cuenta pendiente vigente distinta de efectivo antes de publicar.'))
            if not math.isfinite(payment.amount) or payment.amount <= 0 or payment.currency_id.is_zero(payment.amount):
                raise UserError(_('El importe del pago debe ser positivo, finito y significativo en su moneda.'))
        immutable = payments.read(['id', 'date', 'amount', 'company_id', 'currency_id',
                                   'journal_id', 'payment_type', 'partner_type', 'partner_id',
                                   'partner_bank_id', 'payment_method_line_id'])
        # Both providers support removing draft membership. Releasing it only
        # inside this savepoint lets account.payment.action_post run its normal
        # checks and journal creation, without weakening the direct-FK guard.
        payments.write({'batch_payment_id': False})
        payments.action_post()
        payments.invalidate_recordset(['state', 'move_id', 'is_sent', 'is_matched'])
        moves = payments.move_id
        moves.check_access('read')
        moves.check_field_access_rights('read', ['state', 'company_id', 'origin_payment_id'])
        if (len(moves) != len(payments) or any(payment.state != 'in_process' or not payment.move_id
                or payment.move_id.state != 'posted' or payment.is_sent or payment.is_matched
                or payment.move_id.company_id != company or payment.move_id.origin_payment_id != payment
                for payment in payments)):
            raise UserError(_('El proveedor no devolvió todos los pagos en proceso con sus asientos publicados sin envío.'))
        if payments.read(list(immutable[0].keys())) != immutable:
            raise UserError(_('El proveedor cambió importes, fechas o referencias de los pagos originales.'))
        for batch in batches:
            current = payments.browse(selections[batch.id])
            current.write({'batch_payment_id': batch.id})
            batch.invalidate_recordset(['state', 'payment_ids'])
            if batch.state != 'draft' or self._group_payment_ids(batch) != selections[batch.id]:
                raise UserError(_('El proveedor no conservó exactamente el grupo original en borrador.'))
            self._log_group_payment_posting(batch, current)
        return {'batch_ids': batches.ids, 'payment_ids': payments.ids, 'move_ids': moves.ids}

    @api.model
    def _log_group_payment_posting(self, batch, payments):
        batch.with_context(mail_notify_force_send=False, mail_post_autofollow=False,
                           mail_create_nosubscribe=True).message_post(
            body=_('Se publicaron contablemente %(count)s pagos existentes. El grupo permanece en borrador; '
                   'no se validó, envió ni concilió el lote.', count=len(payments)),
            message_type='comment', subtype_xmlid='mail.mt_note', partner_ids=[])
