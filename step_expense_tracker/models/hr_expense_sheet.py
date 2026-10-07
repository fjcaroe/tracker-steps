import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from .expense_vehicle_line import IMPORT_CONTEXT

_logger = logging.getLogger(__name__)


class HrExpenseSheet(models.Model):
    _inherit = 'hr.expense.sheet'

    tracker_line_count = fields.Integer(string='Recorridos de Tracker', compute='_compute_tracker_line_count')

    @api.depends('vehicle_line_ids.usage_id')
    def _compute_tracker_line_count(self):
        for sheet in self:
            sheet.tracker_line_count = len(sheet.vehicle_line_ids.filtered('usage_id'))

    def _step_tracker_log(self, body):
        """Deja constancia en el chatter sin que un problema de correo del usuario bloquee la operación."""
        self.ensure_one()
        try:
            with self.env.cr.savepoint():
                self.message_post(body=body)
        except UserError:
            _logger.info('No se pudo registrar el mensaje de Tracker en la rendición %s', self.id)

    def action_import_tracker_usage(self):
        self.ensure_one()
        if self.state != 'draft':
            raise UserError(_('Solo se pueden traer recorridos a una rendición en borrador.'))
        return {
            'type': 'ir.actions.act_window', 'name': _('Traer desde Tracker'),
            'res_model': 'step.expense.tracker.import', 'view_mode': 'form', 'target': 'new',
            'context': {'default_sheet_id': self.id},
        }

    @staticmethod
    def _step_value_differs(line, key, value):
        current = line[key]
        if isinstance(current, models.BaseModel):
            current = current.id
        if isinstance(value, float):
            return abs((current or 0.0) - value) > 1e-6
        return (current or False) != (value or False)

    def action_refresh_tracker_lines(self):
        """Actualización EXPLÍCITA desde los usos ya sincronizados, solo en borrador. Las líneas
        corregidas a mano no se tocan; cada cambio queda registrado en el chatter."""
        self.ensure_one()
        if self.state != 'draft':
            raise UserError(_('Solo se puede actualizar desde Tracker una rendición en borrador.'))
        Wizard = self.env['step.expense.tracker.import']
        updated, skipped = [], []
        for line in self.vehicle_line_ids.filtered('usage_id'):
            tag = line.usage_id.session_uuid[:8]
            if line.is_modified:
                skipped.append(tag)
                continue
            values = Wizard._line_values_from_usage(line.usage_id, use_refill=line.liters_source == 'work_order_refill')
            for key in ('imported_at', 'imported_by_id'):
                values.pop(key)
            if any(self._step_value_differs(line, key, value) for key, value in values.items()):
                line.with_context(**{IMPORT_CONTEXT: True}).write(values)
                updated.append(tag)
        self._step_tracker_log(_(
            'Actualización desde Tracker: %(updated)s línea(s) actualizada(s) (%(ids)s); '
            '%(skipped)s con correcciones manuales sin cambios.'
        ) % {'updated': len(updated), 'ids': ', '.join(updated) or '-', 'skipped': len(skipped)})
        return True
