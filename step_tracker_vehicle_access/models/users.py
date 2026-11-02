from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError


class Users(models.Model):
    _inherit = 'res.users'

    tracker_restricted = fields.Boolean(string='Limitar Tracker a vehículos asignados',
        groups='base.group_system,step_tracker_portal.group_tracker_manager')
    tracker_starter_control = fields.Boolean(string='Permitir control del motor de arranque',
        groups='base.group_system,step_tracker_portal.group_tracker_manager')
    tracker_control_preview = fields.Boolean(string='Vista de prueba: sin órdenes físicas',
        groups='base.group_system,step_tracker_portal.group_tracker_manager')
    tracker_vehicle_ids = fields.Many2many('fleet.vehicle', 'step_tracker_user_vehicle_rel',
        'user_id', 'vehicle_id', string='Vehículos autorizados en Tracker',
        groups='base.group_system,step_tracker_portal.group_tracker_manager')

    def _tracker_is_limited(self):
        self.ensure_one()
        user = self.sudo()
        if not user.has_group('step_tracker_portal.group_tracker_viewer'):
            return False
        return user.tracker_restricted or not (user.has_group('base.group_system') or
            user.has_group('step_tracker_portal.group_tracker_manager'))

    def _tracker_vehicle_domain(self, field='id'):
        self.ensure_one()
        return [(field, 'in', self.sudo().tracker_vehicle_ids.ids)] if self._tracker_is_limited() else []

    def _tracker_allowed_asset_ids(self, company=None):
        self.ensure_one()
        user = self.sudo()
        domain = [('active', '=', True), ('vehicle_id', 'in', user.tracker_vehicle_ids.ids),
            ('company_id', 'in', user.company_ids.ids)]
        if company:
            domain.append(('company_id', '=', company.id))
        return self.env['step.tracker.asset.link'].sudo().search(domain).mapped('asset_id')

    def _tracker_portal_access(self, company):
        self.ensure_one()
        user = self.sudo()
        if company not in user.company_ids:
            raise AccessError(_('Compañía no autorizada.'))
        manager = user.has_group('base.group_system') or user.has_group('step_tracker_portal.group_tracker_manager')
        operator = user.has_group('step_tracker_portal.group_tracker_operator')
        viewer = user.has_group('step_tracker_portal.group_tracker_viewer')
        if not (manager or operator or viewer):
            raise AccessError(_('Solicita acceso a Tracker al administrador.'))
        limited = self._tracker_is_limited()
        return {'role': 'manager' if manager and not limited else 'operator' if operator else 'viewer',
            'asset_ids': self._tracker_allowed_asset_ids(company) if limited else None,
            'manage_protection': manager and not limited or user.has_group('step_tracker_vehicle_access.group_vehicle_operator'),
            'starter_control': bool(user.tracker_starter_control or manager and not limited) and not user.tracker_control_preview,
            'control_preview': bool(user.tracker_control_preview)}

    def _tracker_check_asset(self, company, asset_id):
        if self._tracker_is_limited() and asset_id not in self._tracker_allowed_asset_ids(company):
            raise AccessError(_('Vehículo no autorizado.'))

    @api.constrains('tracker_vehicle_ids', 'company_ids')
    def _check_tracker_companies(self):
        for user in self.sudo():
            if any(v.company_id not in user.company_ids for v in user.tracker_vehicle_ids):
                raise ValidationError(_('Los vehículos deben pertenecer a compañías autorizadas del usuario.'))

    def write(self, values):
        if {'tracker_restricted', 'tracker_vehicle_ids', 'tracker_starter_control', 'tracker_control_preview'} & values.keys():
            if not (self.env.user.has_group('base.group_system') or self.env.user.has_group('step_tracker_portal.group_tracker_manager')):
                raise AccessError(_('Solo un administrador de Tracker puede asignar vehículos.'))
        result = super().write(values)
        if {'tracker_restricted', 'tracker_vehicle_ids', 'groups_id', 'company_ids'} & values.keys():
            self.env['ir.rule'].clear_caches() if hasattr(self.env['ir.rule'], 'clear_caches') else self.env.registry.clear_cache()
        return result
