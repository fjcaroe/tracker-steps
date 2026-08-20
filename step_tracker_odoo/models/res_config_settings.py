from odoo import fields, models, _


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    step_tracker_base_url = fields.Char(related='company_id.step_tracker_base_url', readonly=False)
    step_tracker_username = fields.Char(related='company_id.step_tracker_username', readonly=False)
    step_tracker_password = fields.Char(related='company_id.step_tracker_password', readonly=False)
    step_tracker_sync_enabled = fields.Boolean(related='company_id.step_tracker_sync_enabled', readonly=False)

    def action_step_tracker_sync_now(self):
        self.ensure_one()
        counts = self.env['step.tracker.sync'].run_sync()
        message = _(
            'Sincronizado: %(machines)s máquinas, %(drivers)s conductores, '
            '%(activities)s actividades, %(labors)s labores, %(implements)s implementos, '
            '%(fields)s predios, %(sessions)s sesiones y %(work_orders)s partes.'
        ) % counts
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {'title': _('Steps Tracker'), 'message': message, 'sticky': False, 'type': 'success'},
        }
