# © 2025 (Jamie Escalante <jamie.escalante7@gmail.com>)
# -*- coding: utf-8 -*-

import base64
from odoo import api, fields, models, tools, SUPERUSER_ID, _, Command


class StepMachineryTracking(models.Model):
    _name = 'step.machinery.tracking'

    name = fields.Char(string='Nombre', index=True, required=True)
    date = fields.Date(string='Fecha')
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
