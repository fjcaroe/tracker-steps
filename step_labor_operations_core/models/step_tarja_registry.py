# © 2025 (Jamie Escalante <jamie.escalante7@gmail.com>)
# -*- coding: utf-8 -*-

import base64
from odoo import api, fields, models, tools, SUPERUSER_ID, _, Command


class StepTarjaRegistry(models.Model):
    _name = 'step.tarja.registry'
    _rec_name = 'employee_id'

    employee_id = fields.Many2one('hr.employee', 'Empleado')
    contract_id = fields.Many2one(
        'hr.contract', string='Contrato',
        domain="[('employee_id', '=', employee_id)]", help='Current contract of the employee',
        copy=False)
    tarja_id = fields.Many2one(
        comodel_name='step.tarja',
        string="tarja Reference",
        required=True, ondelete='cascade', index=True, copy=False)
    cost_id = fields.Many2one(
        'account.analytic.account', "Centro costos",
    )
    labor_id = fields.Many2one('product.template', 'Labor/Tarea', required=False)
    uom_id = fields.Many2one('uom.uom', 'UdM', required=False)
    quantity = fields.Float(string='Cantidad')
    hrs = fields.Float(string='Hrs. Ord.')
    hrs_extra = fields.Float(string='Hrs. Extra')
    hrs_total = fields.Float(string='Total Hrs.')