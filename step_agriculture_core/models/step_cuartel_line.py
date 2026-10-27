# Â© 2025 (Jamie Escalante <jamie.escalante7@gmail.com>)
# -*- coding: utf-8 -*-

from odoo import api, Command, fields, models, _

class StepCuartelLine(models.Model):
    _name = 'step.cuartel.line'

    name = fields.Char(string='Cuartel', index=True, required=True)
    centro_id = fields.Many2one(
        comodel_name='account.analytic.account',
        string="Centro de costo",
        required=True, ondelete='cascade', index=True, copy=False)
    has_cuartel = fields.Float(string='Has Cuartel', digits=(16, 2))
    plant_cuartel = fields.Integer(string='Plantas Cuartel')
    hilera_cuartel = fields.Integer(string='Hileras Cuartel')
    dis_plant = fields.Char(string='Distancia PlantaciÃ³n')
    clon = fields.Char(string='Clon')
    conduc = fields.Char(string='ConducciÃ³n')
    patron = fields.Char(string='PatrÃ³n')