from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    step_tracker_base_url = fields.Char(
        string='URL API Web Tracker',
        help='URL del backend, sin barra final. Ej: https://stepsapp.cl/tracker-steps',
    )
    step_tracker_username = fields.Char(string='Usuario de servicio Web Tracker')
    step_tracker_password = fields.Char(string='Contraseña de servicio Web Tracker')
    step_tracker_sync_enabled = fields.Boolean(string='Sincronización automática activa', default=False)
