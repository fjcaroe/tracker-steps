# © 2025 (Jamie Escalante <jamie.escalante7@gmail.com>)
# -*- coding: utf-8 -*-

import base64
from odoo import api, fields, models, tools, SUPERUSER_ID, _, Command


class StepLaborLine(models.Model):
    _name = 'step.labor.line'

    name = fields.Char(string='Descripción', index=True, required=True)
    labor_id = fields.Many2one(
        comodel_name='product.template',
        string="Labor Reference",
        required=True, ondelete='cascade', index=True, copy=False)
