# © 2025 (Jamie Escalante <jamie.escalante7@gmail.com>)
# -*- coding: utf-8 -*-

from odoo import api, Command, fields, models, _

class StepCuartelLine(models.Model):
    _name = 'step.cuartel.line'

    name = fields.Char(string='Cuartel', index=True, required=True)
    centro_id = fields.Many2one(
        comodel_name='account.analytic.account',
        string="Centro de costo",
        required=True, ondelete='cascade', index=True, copy=False)
    has_cuartel = fields.Integer(string='Has Cuartel')
    plant_cuartel = fields.Integer(string='Plantas Cuartel')
    hilera_cuartel = fields.Integer(string='Hileras Cuartel')
    dis_plant = fields.Char(string='Distancia Plantación')
    clon = fields.Char(string='Clon')
    conduc = fields.Char(string='Conducción')
    patron = fields.Char(string='Patrón')