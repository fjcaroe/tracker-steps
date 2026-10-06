"""T53: use native actions consistently, preserving all historical Studio data."""
from odoo import api, models


class ManagementDashboard(models.Model):
    _inherit = 'step.management.dashboard'

    @api.model
    def _normalize_management_menus(self):
        root = self.env.ref('step_management_costs.menu_management_root')
        descendants = self.env['ir.ui.menu'].with_context(active_test=False).search([('id', 'child_of', root.id)])
        legacy = self.env['ir.model.data'].search([
            ('model', '=', 'ir.ui.menu'), ('module', '=', 'studio_customization'), ('res_id', 'in', descendants.ids),
        ])
        # Only legacy menus embedded in this app are retired. No Studio models,
        # business records, views, other apps or old actions are deleted.
        self.env['ir.ui.menu'].browse(legacy.mapped('res_id')).exists().write({'active': False})
