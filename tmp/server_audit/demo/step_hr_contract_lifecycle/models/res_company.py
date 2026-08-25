# -*- coding: utf-8 -*-
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    legal_calendar_responsible_id = fields.Many2one(
        "res.users",
        string="Responsable RR. HH. calendario legal",
        help="Recibe las actividades de alerta (180/90/60/30/15/7 días) y "
        "las incidencias críticas del calendario legal laboral. Si se "
        "deja vacío, las alertas quedan asignadas a quien ejecuta el cron.",
    )
