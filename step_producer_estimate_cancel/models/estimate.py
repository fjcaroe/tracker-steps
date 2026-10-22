"""T107: explicit cancellation without deleting or reviving version history."""
from odoo import api, fields, models, _
from odoo.exceptions import UserError

_CANCEL = object()
_AUDIT = {'estimate_cancelled_at', 'estimate_cancelled_by_id'}


def preserve_cancelled(records):
    if records:
        raise UserError(_('Conserve el módulo de anulación mientras existan estimaciones anuladas.'))


def reject_cancelled(estimates):
    if any(record.state == 'cancelled' for record in estimates):
        raise UserError(_('La estimación anulada conserva sus datos históricos.'))


class Estimate(models.Model):
    _inherit = 'step.export.estimate'

    state = fields.Selection(selection_add=[('cancelled', 'Anulada')],
                             ondelete={'cancelled': preserve_cancelled})
    estimate_cancelled_at = fields.Datetime(string='Anulada el', readonly=True, copy=False)
    estimate_cancelled_by_id = fields.Many2one('res.users', string='Anulada por', readonly=True, copy=False)

    @api.model_create_multi
    def create(self, values_list):
        if any(values.get('state') == 'cancelled' or _AUDIT.intersection(values) for values in values_list):
            raise UserError(_('Use Anular estimación sobre una estimación existente.'))
        return super().create(values_list)

    def write(self, values):
        # The private object cannot be forged through an RPC context.
        transition = self.env.context.get('_estimate_cancellation') is _CANCEL
        if not transition and (values.get('state') == 'cancelled' or _AUDIT.intersection(values)):
            raise UserError(_('Use el botón Anular estimación.'))
        if values and any(record.state == 'cancelled' for record in self):
            # Chatter attachments may still be linked; business data stay frozen.
            if set(values) - {'message_main_attachment_id'}:
                reject_cancelled(self)
        return super().write(values)

    def unlink(self):
        reject_cancelled(self)
        return super().unlink()

    def action_cancel_estimate(self):
        self.check_access('write')
        if any(record.company_id not in self.env.companies for record in self):
            raise UserError(_('La estimación no pertenece a una empresa activa.'))
        if self:
            self.env.cr.execute('SELECT id FROM step_export_estimate WHERE id=ANY(%s) ORDER BY id FOR UPDATE', (self.ids,))
            self.invalidate_recordset(['state'])
        pending = self.filtered(lambda record: record.state != 'cancelled')
        if any(record.state not in ('created', 'validated', 'current') for record in pending):
            raise UserError(_('Una versión reemplazada ya es histórica y no se puede anular.'))
        if pending:
            pending.with_context(_estimate_cancellation=_CANCEL).write({
                'state': 'cancelled', 'estimate_cancelled_at': fields.Datetime.now(),
                'estimate_cancelled_by_id': self.env.uid})
        return True


class EstimateLine(models.Model):
    _inherit = 'step.export.estimate.line'

    def _check_editable(self):
        reject_cancelled(self.mapped('estimate_id'))
        return super()._check_editable()

    @api.model_create_multi
    def create(self, values_list):
        reject_cancelled(self.env['step.export.estimate'].browse([
            values['estimate_id'] for values in values_list if values.get('estimate_id')]))
        return super().create(values_list)

    def write(self, values):
        if values:
            reject_cancelled(self.mapped('estimate_id'))
            reject_cancelled(self.env['step.export.estimate'].browse(values.get('estimate_id', [])))
        return super().write(values)


class EstimateWeek(models.Model):
    _inherit = 'step.export.estimate.week'

    def _check_editable(self):
        reject_cancelled(self.mapped('line_id.estimate_id'))
        return super()._check_editable()

    @api.model_create_multi
    def create(self, values_list):
        lines = self.env['step.export.estimate.line'].browse([
            values['line_id'] for values in values_list if values.get('line_id')])
        reject_cancelled(lines.mapped('estimate_id'))
        return super().create(values_list)

    def write(self, values):
        if values.get('line_id'):
            reject_cancelled(self.env['step.export.estimate.line'].browse(values['line_id']).mapped('estimate_id'))
        return super().write(values)


class EstimateReport(models.Model):
    _inherit = 'step.producer.estimate.report'

    state = fields.Selection(selection_add=[('cancelled', 'Anulada')],
                             ondelete={'cancelled': preserve_cancelled})
