# © 2025 (Jamie Escalante <jamie.escalante7@gmail.com>)
# -*- coding: utf-8 -*-

import base64
from odoo import api, fields, models, tools, SUPERUSER_ID, _, Command
from odoo.exceptions import ValidationError


class StepCosechaProcesoLine(models.Model):
    _name = 'step.cosecha.proceso.line'
    _description = 'Control de Proceso Postcosecha'
    _order = 'date_tarja_init, id'
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
            ('translado', 'Traslado Cosecha'),
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
    duration_hours = fields.Float(
        string='Duración (h)', compute='_compute_duration_hours', store=True,
        digits=(12, 2)
    )

    @api.depends('date_tarja_init', 'date_tarja_end')
    def _compute_duration_hours(self):
        for line in self:
            if line.date_tarja_init and line.date_tarja_end:
                delta = line.date_tarja_end - line.date_tarja_init
                line.duration_hours = max(delta.total_seconds() / 3600.0, 0.0)
            else:
                line.duration_hours = 0.0

    @api.constrains('date_tarja_init', 'date_tarja_end')
    def _check_process_dates(self):
        for line in self:
            if (
                line.date_tarja_init
                and line.date_tarja_end
                and line.date_tarja_end < line.date_tarja_init
            ):
                raise ValidationError(_(
                    "La fecha de término no puede ser anterior a la fecha de inicio."
                ))
