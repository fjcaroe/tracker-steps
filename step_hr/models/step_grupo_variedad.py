# © 2025 (Jamie Escalante <jamie.escalante7@gmail.com>)
# -*- coding: utf-8 -*-

import base64
from odoo import api, fields, models, tools, SUPERUSER_ID, _, Command


class StepGrupoVariedad(models.Model):
    _name = 'step.grupo.variedad'
    _inherit = ['mail.thread']

    name = fields.Char(string='Nombre', index=True, required=True)
    especie_id = fields.Many2one('step.especie',
        string="Especie",
        required=True, ondelete='cascade', copy=False)
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    #tags_ids
    note = fields.Html(string="Notas")
    variedad_line = fields.One2many(
        comodel_name='step.grupo.variedad.line',
        inverse_name='grupo_variedad_id',
        string="Grupo Variedad Lines",
        copy=True, auto_join=True)