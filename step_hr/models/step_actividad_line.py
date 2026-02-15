# © 2025 (Jamie Escalante <jamie.escalante7@gmail.com>)
# -*- coding: utf-8 -*-

import base64
from odoo import api, fields, models, tools, SUPERUSER_ID, _, Command


class StepActividadLine(models.Model):
    _name = 'step.actividad.line'

    name = fields.Char(string='Linea', index=True, required=True)
    labor_id = fields.Many2one('product.template', 'Labor/Tarea', required=True)
    actividad_id = fields.Many2one(
        comodel_name='step.actividad',
        string="Actividad Reference",
        required=True, ondelete='cascade', index=True, copy=False)