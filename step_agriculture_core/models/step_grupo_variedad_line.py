# © 2025 (Jamie Escalante <jamie.escalante7@gmail.com>)
# -*- coding: utf-8 -*-

import base64
from odoo import api, fields, models, tools, SUPERUSER_ID, _, Command


class StepGrupoVariedadLine(models.Model):
    _name = 'step.grupo.variedad.line'

    name = fields.Char(string='Descripción', index=True, required=True)
    uom_id = fields.Many2one('uom.uom', 'UdM', required=True)
    uom_trato = fields.Many2one('uom.uom', 'Unidad trato', required=True)
    labor_id = fields.Many2one('product.template', 'Labor/Tarea', required=True)
    hec_rendimiento = fields.Integer(string='Redim. standar')
    grupo_variedad_id = fields.Many2one(
        comodel_name='step.grupo.variedad',
        string="Grupo Variedad Reference",
        required=True, ondelete='cascade', index=True, copy=False)
