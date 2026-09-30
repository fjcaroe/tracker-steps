from odoo import _, api, fields, models
from odoo.exceptions import UserError


class FleetVehicle(models.Model):
    _inherit = 'fleet.vehicle'

    tracker_asset_link_ids = fields.One2many('step.tracker.asset.link', 'vehicle_id', string='Activos de Tracker')
    tracker_asset_id = fields.Char(string='Activo en Tracker', compute='_compute_tracker_asset_id')

    @api.depends('tracker_asset_link_ids.active', 'tracker_asset_link_ids.asset_id', 'company_id')
    def _compute_tracker_asset_id(self):
        for vehicle in self:
            link = vehicle.tracker_asset_link_ids.filtered(
                lambda l: l.active and (not vehicle.company_id or l.company_id == vehicle.company_id))[:1]
            vehicle.tracker_asset_id = link.asset_id or False

    def action_open_tracker_map(self):
        """Abre el portal con el activo preseleccionado (el portal lee ``?asset=``)."""
        self.ensure_one()
        if not self.tracker_asset_id:
            raise UserError(_('Este vehículo no está vinculado a un activo de Tracker.'))
        return {'type': 'ir.actions.act_url', 'url': '/web_tracker/?asset=%s#fleet' % self.tracker_asset_id, 'target': 'self'}

    def action_open_tracker_costs(self):
        self.ensure_one()
        return self.env['step.tracker.cost.wizard'].action_open(scope='vehicle', vehicle=self)
