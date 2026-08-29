# © 2025 (Jamie Escalante <jamie.escalante7@gmail.com>)
# -*- coding: utf-8 -*-

import base64
from odoo import api, fields, models, tools, SUPERUSER_ID, _, Command


class MonthlyConsumptionLine(models.Model):
    _name = 'monthly.consumption.line'

    name = fields.Char(string='Nombre', index=True, required=True)
    service_machinery_id = fields.Many2one('type.service.machinery', string='Concepto Maquinaria', required=False)
    concept_amount = fields.Float(string='Monto Concepto')
    cost_hr_amount = fields.Float(string='Costo Hr Mq')
    vehicle_id = fields.Many2one(
        comodel_name='fleet.vehicle',
        string="Vehicle Reference",
        required=True, ondelete='cascade', index=True, copy=False)
