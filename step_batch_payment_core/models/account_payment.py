from odoo import _, api, fields, models
from odoo.exceptions import UserError


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    batch_payment_id = fields.Many2one('account.batch.payment', copy=False, ondelete='set null')

    @api.model_create_multi
    def create(self, values_list):
        if self.env.context.get('default_batch_payment_id') or any(values.get('batch_payment_id') for values in values_list):
            raise UserError(_('Cree primero el pago; un grupo sólo selecciona pagos existentes.'))
        return super().create(values_list)

    def write(self, values):
        self.check_access('write')
        service = self.env['step.batch.payment.grouping']
        if 'batch_payment_id' in values:
            if set(values) != {'batch_payment_id'}:
                raise UserError(_('La selección de un grupo sólo puede cambiar la relación del pago.'))
            payments = service._lock_payments(self.ids)
            for batch in payments.batch_payment_id:
                service._lock_batch(batch.id)
            if values['batch_payment_id']:
                batch = service._lock_batch(values['batch_payment_id'])
                service._validate_payments(payments, batch)
                existing = service._group_payments(batch)
                service._validate_payments(existing | payments, batch)
        elif self.batch_payment_id and set(values) & {
                'amount', 'currency_id', 'company_id', 'journal_id', 'payment_type',
                'payment_method_line_id', 'payment_method_id', 'move_id', 'state', 'is_sent', 'is_matched'}:
            raise UserError(_('Separe primero el pago del grupo para modificar su información contable o estado.'))
        return super().write(values)

    def unlink(self):
        if self.batch_payment_id:
            raise UserError(_('Separe primero el pago de su grupo; eliminar un grupo no elimina pagos.'))
        return super().unlink()
