import hashlib
import json

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError


class HarvestMobileLifecycle(models.Model):
    _inherit = 'step.cosecha.registry'

    _HARVEST_AUDIT_FIELDS = frozenset({
        'mobile_status', 'mobile_state_date', 'mobile_state_user_id', 'mobile_approved_by_id',
        'mobile_approved_at', 'mobile_native_approval', 'mobile_approved_manifest',
        'mobile_approved_delivery_count',
    })

    mobile_status = fields.Selection(tracking=True)
    mobile_state_date = fields.Datetime(string='Último cambio Harvest', readonly=True, copy=False)
    mobile_state_user_id = fields.Many2one('res.users', string='Actualizado por', readonly=True, copy=False)
    mobile_approver_id = fields.Many2one('res.users', string='Aprobador', copy=False, tracking=True)
    mobile_approved_by_id = fields.Many2one('res.users', string='Aprobado por', readonly=True, copy=False, tracking=True)
    mobile_approved_at = fields.Datetime(string='Fecha de aprobación', readonly=True, copy=False, tracking=True)
    mobile_native_approval = fields.Boolean(string='Aprobación nativa desde Harvest', readonly=True, copy=False)
    mobile_approved_manifest = fields.Char(string='Huella de entregas aprobadas', readonly=True, copy=False, tracking=True)
    mobile_approved_delivery_count = fields.Integer(string='Entregas aprobadas', readonly=True, copy=False, tracking=True)

    def _harvest_valid_approver(self, user):
        self.ensure_one()
        if not user or not user.active or user.share or self.company_id not in user.company_ids:
            return False
        try:
            self.with_user(user).with_context(allowed_company_ids=self.company_id.ids).check_access('write')
        except AccessError:
            return False
        return True

    @api.constrains('mobile_approver_id', 'company_id')
    def _check_harvest_approver(self):
        for order in self.filtered('mobile_approver_id'):
            if not order._harvest_valid_approver(order.mobile_approver_id):
                raise ValidationError(_('El aprobador debe ser un usuario interno activo con acceso de escritura a esta OT y su empresa.'))

    def write(self, values):
        if not self.env.su and self._HARVEST_AUDIT_FIELDS.intersection(values):
            raise AccessError(_('Use las acciones de Harvest para cambiar el estado o su auditoría.'))
        if 'mobile_approver_id' in values:
            for order in self:
                if (order.mobile_status == 'sent' or order.mobile_status == 'reviewed' and order.mobile_approved_by_id) and values['mobile_approver_id'] != order.mobile_approver_id.id:
                    raise ValidationError(_('Reabra la OT antes de cambiar su aprobador. Una OT enviada conserva su aprobación.'))
        return super().write(values)

    @api.model_create_multi
    def create(self, values_list):
        if not self.env.su:
            for values in values_list:
                if (values.get('mobile_status', 'progress') != 'progress' or
                        any(values.get(key) for key in self._HARVEST_AUDIT_FIELDS - {'mobile_status'})):
                    raise AccessError(_('Una OT nueva debe completar su aprobación y envío mediante las acciones de Harvest.'))
        return super().create(values_list)

    def _harvest_write(self, values):
        """Private transition writer; keeps native ACLs, rules and constraints."""
        return super(HarvestMobileLifecycle, self).write(values)

    def _harvest_approval_values(self):
        identifiers = sorted(self.tarja_registry_line.filtered('mobile_uid').mapped('mobile_uid'))
        return {'mobile_approved_by_id': self.env.uid, 'mobile_approved_at': fields.Datetime.now(),
                'mobile_approved_manifest': hashlib.sha256(json.dumps(identifiers).encode()).hexdigest(),
                'mobile_approved_delivery_count': len(identifiers)}

    def _lock_harvest_order(self):
        self.ensure_one()
        self.check_access('write')
        self.env.cr.execute('SELECT id FROM step_cosecha_registry WHERE id = %s FOR UPDATE', [self.id])
        self.invalidate_recordset(['mobile_status', 'state', 'invoice_id', 'purchase_id',
                                  'mobile_approver_id', 'mobile_approved_by_id', 'mobile_native_approval'])

    def _harvest_transition(self, action, delivery_uuids):
        """Confirm the device manifest against native deliveries before closing.

        Approval calls the native Ingresado -> Aprobado action. Higher ERP states
        are preserved. A transaction lock serializes closure with deliveries.
        """
        self._lock_harvest_order()
        if action == 'review':
            action = 'approve'  # Preserve the previous web client's route.
        transitions = {'close': ('progress', 'closed'), 'approve': ('closed', 'reviewed'),
                       'send': ('reviewed', 'sent'), 'reopen': ('closed', 'progress')}
        if not isinstance(action, str) or action not in transitions:
            raise ValidationError(_('Acción de jornada no válida.'))
        if (not isinstance(delivery_uuids, list) or len(delivery_uuids) > 10000 or
                any(not isinstance(value, str) or not value.strip() for value in delivery_uuids) or
                len(set(delivery_uuids)) != len(delivery_uuids)):
            raise ValidationError(_('La lista de entregas de la jornada no es válida.'))
        lines = self.env['step.cosecha.tarja.registry.line'].search([
            ('registry_id', '=', self.id), ('mobile_uid', 'in', delivery_uuids)])
        if action != 'reopen' and set(lines.mapped('mobile_uid')) != set(delivery_uuids):
            raise ValidationError(_(
                'Odoo aún no confirma todas las entregas de esta OT. Sincronice los pendientes antes de continuar.'))
        source, target = transitions[action]
        current = self.mobile_status or 'progress'
        if action == 'reopen':
            if current == 'sent':
                raise ValidationError(_('Una OT enviada no se puede reabrir.'))
            if current not in ('closed', 'reviewed', 'progress'):
                raise ValidationError(_('La OT no se encuentra disponible para reabrir.'))
            if current == 'progress':
                return
            if self.state == 'apro' and self.mobile_native_approval:
                self.action_in()
            self._harvest_write({'mobile_status': 'progress', 'mobile_approved_by_id': False,
                        'mobile_approved_at': False, 'mobile_native_approval': False,
                        'mobile_approved_manifest': False, 'mobile_approved_delivery_count': 0,
                        'mobile_state_date': fields.Datetime.now(), 'mobile_state_user_id': self.env.uid})
            return
        if action == 'approve':
            approver = self.mobile_approver_id or self.env.user
            if approver != self.env.user or not self._harvest_valid_approver(approver):
                raise AccessError(_('La aprobación debe realizarla el aprobador seleccionado con sus permisos actuales.'))
            if current == 'reviewed' and self.mobile_approved_by_id:
                return
            if current not in ('closed', 'reviewed'):
                raise ValidationError(_('Cierre la OT antes de aprobarla.'))
            if not self.mobile_approver_id:
                self.mobile_approver_id = approver
            native_approval = self.mobile_native_approval
            if self.state == 'in':
                self.action_apro()
                native_approval = True
            self._harvest_write(dict(self._harvest_approval_values(), mobile_native_approval=native_approval,
                            mobile_status='reviewed', mobile_state_date=fields.Datetime.now(),
                            mobile_state_user_id=self.env.uid))
            return
        if current == target:
            return  # A lost HTTP response can be retried without another event.
        if action == 'send' and not self.mobile_approved_by_id:
            raise ValidationError(_('El aprobador debe aprobar esta OT antes de enviarla.'))
        if current != source:
            raise ValidationError(_('Actualice la jornada: su estado cambió o falta completar el paso anterior.'))
        self._harvest_write({'mobile_status': target, 'mobile_state_date': fields.Datetime.now(),
                    'mobile_state_user_id': self.env.uid})
