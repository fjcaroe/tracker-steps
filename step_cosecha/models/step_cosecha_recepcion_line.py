# © 2025 (Jamie Escalante <jamie.escalante7@gmail.com>)
# -*- coding: utf-8 -*-

import base64
from odoo import api, fields, models, tools, SUPERUSER_ID, _, Command


class StepCosechaRecepcionLine(models.Model):
    _name = 'step.cosecha.recepcion.line'
    _rec_name = 'employee_id'

    employee_id = fields.Many2one('hr.employee', 'Empleado')
    # employee_id_domain = fields.Many2many('hr.employee', 'tarja_employee_rel', 'employee_id',
    #                                       'tarja_id', string='Empleados', compute='compute_total_trato')
    recep_id = fields.Many2one(
        comodel_name='step.cosecha.recepcion',
        string="Cosecha",
        required=True, ondelete='cascade', index=True, copy=False)