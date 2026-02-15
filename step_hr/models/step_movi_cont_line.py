# © 2025 (Jamie Escalante <jamie.escalante7@gmail.com>)
# -*- coding: utf-8 -*-

import base64
from odoo import api, fields, models, tools, SUPERUSER_ID, _, Command


class StepMoviContLine(models.Model):
    _name = 'step.movi.cont.line'
    _rec_name = 'employee_id'

    employee_id = fields.Many2one('hr.employee', 'Empleado')
    movi_id = fields.Many2one(
        comodel_name='step.movi.registry',
        string="Movimiento",
        required=True, ondelete='cascade', index=True, copy=False)
    cod_nip = fields.Char(related='employee_id.pin', string='Código NIP')
    cost_id = fields.Many2one(
        'account.analytic.account', "Centro de Costo",
    )
    labor_id = fields.Many2one('product.template', 'Labor/Tarea', required=False)
    hrs_total = fields.Float(string='Horas Totales')
    hrs_porcen = fields.Float(string='Horas %')
    dist_movi = fields.Float(string='Distrib. movilización')