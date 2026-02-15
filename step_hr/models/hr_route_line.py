# © 2025 (Jamie Escalante <jamie.escalante7@gmail.com>)
# -*- coding: utf-8 -*-

from odoo import api, Command, fields, models, _

class HrRouteLine(models.Model):
    _name = 'hr.route.line'

    name = fields.Char(string='Lugar parada', index=True)
    stop_kms = fields.Float(string='Kms')
    route_id = fields.Many2one(
        comodel_name='hr.route',
        string="Route Reference",
        required=True, ondelete='cascade', index=True, copy=False)
