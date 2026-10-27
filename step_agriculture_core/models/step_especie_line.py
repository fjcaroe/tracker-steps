# © 2025 (Jamie Escalante <jamie.escalante7@gmail.com>)
# -*- coding: utf-8 -*-

from odoo import api, Command, fields, models, _

class StepEspecieLine(models.Model):
    _name = 'step.especie.line'

    name = fields.Char(string='Descripción', index=True, required=True)
    especie_id = fields.Many2one(
        comodel_name='step.especie',
        string="Especie Reference",
        required=True, ondelete='cascade', index=True, copy=False)