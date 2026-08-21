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
    kilos_numeric = fields.Float(
        string='Kilos analíticos', compute='_compute_kilos_numeric', store=True
    )
    company_id = fields.Many2one(
        'res.company', string='Empresa', default=lambda self: self.env.company,
        index=True, copy=False
    )

    @api.depends('kilos')
    def _compute_kilos_numeric(self):
        for record in self:
            raw_value = str(record.kilos or '').strip().replace(' ', '')
            if ',' in raw_value:
                raw_value = raw_value.replace('.', '').replace(',', '.')
            try:
                record.kilos_numeric = float(raw_value or 0.0)
            except (TypeError, ValueError):
                record.kilos_numeric = 0.0
