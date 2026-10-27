# © 2025 (Jamie Escalante <jamie.escalante7@gmail.com>)
# -*- coding: utf-8 -*-

import base64
from odoo import api, fields, models, tools, SUPERUSER_ID, _, Command


class StepActividad(models.Model):
    _name = 'step.actividad'
    _inherit = ['mail.thread']

    name = fields.Char(string='Descripción', index=True, required=True)
    cod_actividad = fields.Char(string='Código Actividad')
    cost_id = fields.Many2one(
        'account.analytic.account', "Cuenta analítica",
    )
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    actividad_line = fields.One2many(
        comodel_name='step.actividad.line',
        inverse_name='actividad_id',
        string="Actividad Lines",
        copy=True, auto_join=True)
