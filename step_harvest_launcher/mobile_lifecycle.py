from odoo import fields, models, _
from odoo.exceptions import ValidationError


class HarvestMobileLifecycle(models.Model):
    _inherit = 'step.cosecha.registry'

    mobile_status = fields.Selection(tracking=True)
    mobile_state_date = fields.Datetime(string='Último cambio Harvest', readonly=True, copy=False)
    mobile_state_user_id = fields.Many2one('res.users', string='Actualizado por', readonly=True, copy=False)

    def _lock_harvest_order(self):
        self.ensure_one()
        self.check_access('write')
        self.env.cr.execute('SELECT id FROM step_cosecha_registry WHERE id = %s FOR UPDATE', [self.id])
        self.invalidate_recordset(['mobile_status', 'state', 'invoice_id', 'purchase_id'])

    def _harvest_transition(self, action, delivery_uuids):
        """Confirm the device manifest against native deliveries before closing.

        The ERP approval/costing state is independent. A transaction lock also
        serializes this transition with a mobile delivery arriving concurrently.
        """
        self._lock_harvest_order()
        transitions = {'close': ('progress', 'closed'), 'review': ('closed', 'reviewed'),
                       'send': ('reviewed', 'sent')}
        if not isinstance(action, str) or action not in transitions:
            raise ValidationError(_('Acción de jornada no válida.'))
        if (not isinstance(delivery_uuids, list) or len(delivery_uuids) > 10000 or
                any(not isinstance(value, str) or not value.strip() for value in delivery_uuids) or
                len(set(delivery_uuids)) != len(delivery_uuids)):
            raise ValidationError(_('La lista de entregas de la jornada no es válida.'))
        lines = self.env['step.cosecha.tarja.registry.line'].search([
            ('registry_id', '=', self.id), ('mobile_uid', 'in', delivery_uuids)])
        if set(lines.mapped('mobile_uid')) != set(delivery_uuids):
            raise ValidationError(_(
                'Odoo aún no confirma todas las entregas de esta OT. Sincronice los pendientes antes de continuar.'))
        source, target = transitions[action]
        current = self.mobile_status or 'progress'
        if current == target:
            return  # A lost HTTP response can be retried without another event.
        if current != source:
            raise ValidationError(_('Actualice la jornada: su estado cambió o falta completar el paso anterior.'))
        self.write({'mobile_status': target, 'mobile_state_date': fields.Datetime.now(),
                    'mobile_state_user_id': self.env.uid})
