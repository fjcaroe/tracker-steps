# -*- coding: utf-8 -*-
# Puerto desde Studio (steps_qa) a codigo real - ticket 33 Cerro El Plomo.
from odoo import fields, models


class StepPackingTemperatureControl(models.Model):
    _name = 'step.packing.temperature.control'
    _description = 'Control de Temperatura'
    _order = 'sequence, name'
    _rec_name = 'name'

    name = fields.Char(string='Control de Temperatura', required=True)
    company_id = fields.Many2one('res.company', string='Empresa', default=lambda self: self.env.company)
    sequence = fields.Integer(string='Secuencia', default=10)
    user_id = fields.Many2one('res.users', string='Responsable')
