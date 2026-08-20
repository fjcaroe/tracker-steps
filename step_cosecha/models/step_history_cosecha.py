# © 2026 (Jamie Escalante <jamie.escalante7@gmail.com>)
# -*- coding: utf-8 -*-

import base64
from odoo import api, fields, models, tools, SUPERUSER_ID, _, Command


class StepHistory(models.Model):
    _name = 'step.history.cosecha'
    _inherit = ['mail.thread']

    name = fields.Char(string='Temporada', index=True, required=True)
    fundo = fields.Char(string='Fundo', required=False)
    especie = fields.Char(string='Especie', required=False)
    variedad = fields.Char(string='Variedad', required=False)
    centro_costo = fields.Char(string='Centro de Costo', required=False)
    cuartel = fields.Char(string='Cuartel', required=False)
    fecha = fields.Date(string='Fecha', required=False)
    type_cosecha = fields.Char(string='Tipo Cosecha', required=False)
    envase = fields.Float(string='Envases', required=False)
    kilos = fields.Char(string='Kilos', required=False)
