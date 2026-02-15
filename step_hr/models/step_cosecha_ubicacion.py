# © 2025 (Jamie Escalante <jamie.escalante7@gmail.com>)
# -*- coding: utf-8 -*-

import base64
from odoo import api, fields, models, tools, SUPERUSER_ID, _, Command


class StepCosechaUbicacion(models.Model):
    _name = 'step.cosecha.ubicacion'
    _inherit = ['mail.thread']

    name = fields.Char(string='Nombre', index=True, required=True)
    fundo_id = fields.Many2one('step.fundo',
        string="Fundo",
        required=True, ondelete='cascade', copy=False)
    type_ubicacion = fields.Selection(
        selection=[
            ('rama', 'Ramada'),
            ('aco', 'Acopio'),
            ('cuar', 'Cuartel'),
        ],
        string='Tipo Ubicación',
        required=True,
        readonly=False,
        copy=False,
    )
    responsable_id = fields.Many2one("res.users", string="Responsable")
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)