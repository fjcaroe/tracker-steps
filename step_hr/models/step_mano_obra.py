# © 2025 (Jamie Escalante <jamie.escalante7@gmail.com>)
# -*- coding: utf-8 -*-

import base64
from odoo import api, fields, models, tools, SUPERUSER_ID, _, Command


class StepCosecha(models.Model):
    _name = 'step.cosecha'
    _inherit = ['mail.thread']

    name = fields.Char(string='Nombre', index=True, required=True)
    cost_id = fields.Many2one(
        'account.analytic.account', "Centro de Costo",
    )
    has_cost = fields.Integer(string='Has CCosto')
    plant_cost = fields.Integer(string='Plantas CCosto')
    labor_id = fields.Many2one(
        comodel_name='product.template',
        string="Labor / Tarea",
        required=True, ondelete='cascade', index=True, copy=False)