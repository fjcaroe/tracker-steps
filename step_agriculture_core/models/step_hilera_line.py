# © 2025 (Jamie Escalante <jamie.escalante7@gmail.com>)
# -*- coding: utf-8 -*-

from odoo import api, Command, fields, models, _

class StepHileralLine(models.Model):
    _name = 'step.hilera.line'

    name = fields.Char(string='Hilera', index=True, required=True)
    centro_id = fields.Many2one(
        comodel_name='account.analytic.account',
        string="Centro de costo",
        required=True, ondelete='cascade', index=True, copy=False)
    cuartel_id = fields.Many2one(
        comodel_name='step.cuartel.line',
        string="Cuartel",
        required=True, ondelete='cascade')
    plat_hilera = fields.Integer(string='Plantas Hileras')
    mtrs_hilera = fields.Integer(string='Metros Hilera')