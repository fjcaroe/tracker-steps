# © 2025 (Jamie Escalante <jamie.escalante7@gmail.com>)
# -*- coding: utf-8 -*-

import base64
from odoo import api, fields, models, tools, SUPERUSER_ID, _, Command


class StepCosechaProcesoLine(models.Model):
    _name = 'step.cosecha.proceso.line'
    # _rec_name = 'employee_id'

    name = fields.Char(string='Descripción', index=True, required=True)
    proceso_id = fields.Many2one(
        comodel_name='step.cosecha.proceso',
        string="Cosecha Proceso",
        required=True, ondelete='cascade', index=True, copy=False)
    pro_cosecha = fields.Selection(
        selection=[
            ('control', 'Control T'),
            ('calidad_co', 'Control Calidad'),
            ('fumi', 'Fumigación'),
            ('translado', 'Tranlado Cosecha'),
        ],
        string='Proceso Cosecha',
        required=False,
        readonly=False,
        copy=False
    )
    num_tarja = fields.Char(string='Num. Tarja')
    date_tarja_init = fields.Datetime(string='Fecha hora Inicio')
    date_tarja_end = fields.Datetime(string='Fecha hora Termino')
    temp = fields.Float(string='Temperatura')
    calidad = fields.Selection(
        selection=[
            ('aprueba', 'Aprueba'),
            ('rechaza', 'Rechaza')
        ],
        string='Calidad',
        required=False,
        readonly=False,
        copy=False
    )
    comment = fields.Html(string="Comentarios")