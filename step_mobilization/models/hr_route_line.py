# -*- coding: utf-8 -*-

from odoo import fields, models


class HrRouteLine(models.Model):
    _name = 'hr.route.line'
    _description = 'Parada de un recorrido'
    _order = 'sequence, id'

    name = fields.Char(string='Lugar parada', index=True, required=True)
    sequence = fields.Integer(string='Orden', default=10)
    stop_kms = fields.Float(string='Kms')
    latitude = fields.Float(string='Latitud', digits=(10, 7))
    longitude = fields.Float(string='Longitud', digits=(10, 7))
    geofence_radius = fields.Integer(string='Radio geocerca (m)', default=100)
    route_id = fields.Many2one('hr.route', string="Recorrido",
                                required=True, ondelete='cascade', index=True, copy=False)
