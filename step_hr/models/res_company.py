# © 2025 (Jamie Escalante <jamie.escalante7@gmail.com>)
# -*- coding: utf-8 -*-

from odoo import api, models, fields, _
from odoo.exceptions import UserError, ValidationError, RedirectWarning

class ResCompany(models.Model):
    _inherit = "res.company"

    # Integración Web Tracker (monitoreo GPS de maquinaria agrícola)
    step_tracker_base_url = fields.Char(
        string='URL API Web Tracker',
        help='URL del backend de Web Tracker, sin barra final. '
             'Ej: https://stepsapp.cl/tracker-api (NO la URL del sitio web_tracker/).')
    step_tracker_username = fields.Char(string='Usuario de servicio Web Tracker')
    step_tracker_password = fields.Char(string='Contraseña de servicio Web Tracker')
    step_tracker_sync_enabled = fields.Boolean(string='Sincronización automática activa', default=False)
