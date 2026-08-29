# -*- coding: utf-8 -*-

from odoo import fields, models


class FleetVehicle(models.Model):
    _inherit = 'fleet.vehicle'

    step_min_pass = fields.Integer('Mínimo pasajeros sentados')
    step_max_pass = fields.Integer('Máximo pasajeros sentados')
    step_mobilization_enabled = fields.Boolean(
        string='Habilitado para movilización de personal', default=False,
        help='Marca los vehículos que este transportista puede usar para transportar '
             'trabajadores; separa la flota de pasajeros de la de carga/maquinaria.')
