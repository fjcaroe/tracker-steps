# © 2025 (Jamie Escalante <jamie.escalante7@gmail.com>)
# -*- coding: utf-8 -*-

import base64
from odoo import api, fields, models, tools, SUPERUSER_ID, _, Command


class StepVariedad(models.Model):
    _name = 'step.variedad'
    _inherit = ['mail.thread']

    name = fields.Char(string='Nombre', index=True, required=True)
    cod_variedad = fields.Char(string='Código Variedad', required=True)
    especie_id = fields.Many2one('step.especie',
        string="Especie",
        required=True, ondelete='cascade', copy=False)
    grupo_variedad_id = fields.Many2one('step.grupo.variedad',
        string="Grupo Variedad",
        required=True, ondelete='cascade', copy=False)
    date_init = fields.Date(string='Inicio Cosecha')
    partner_id = fields.Many2one('res.partner', 'Responsable')
    company_id = fields.Many2one('res.company', string='Empresa', required=True, default=lambda self: self.env.company)
    #tags_ids
    note = fields.Html(string="Notas")
    date_to = fields.Date(string='Final Cosecha')
    variedad_line = fields.One2many(
        comodel_name='step.variedad.line',
        inverse_name='variedad_id',
        string="Variedad Lines",
        copy=True, auto_join=True)