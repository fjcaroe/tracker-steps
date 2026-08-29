# © 2025 (Jamie Escalante <jamie.escalante7@gmail.com>)
# -*- coding: utf-8 -*-

import base64
from odoo import api, fields, models, tools, SUPERUSER_ID, _, Command


class RegistCostMachineryLine(models.Model):
    _name = 'regist.cost.machinery.line'
    _rec_name = 'machinery_ids'

    @api.depends('hrs_maquina','odometer_end','odometer_end')
    def compute_total_costo(self):
        eta_list = []
        hora_extra = 0
        for move in self:
            move.cost_hrs_maquina = float(move.hrs_maquina) * float(move.regist_cost_id.total_cost)
            move.cost_odometer = float(move.odometer_end) - float(move.odometer_init)

    machinery_ids = fields.Many2one(
        comodel_name='fleet.vehicle',
        string="Maquinaria",
        required=True, ondelete='cascade', index=True, copy=True)
    implement_id = fields.Many2one(
        comodel_name='step.machinery.implement',
        string="Implemento",
        required=False, ondelete='cascade', index=True, copy=True)
    employee_id = fields.Many2one('hr.employee', 'Conductor')
    cost_id = fields.Many2one(
        'account.analytic.account', "Centro costos",
    )
    labor_id = fields.Many2one('step.labor', 'Labor', required=False)
    actividad_id = fields.Many2one(related='labor_id.actividad_id', string='Actividad',
    )
    date = fields.Date(string='Fecha')
    uom_id = fields.Many2one(related='labor_id.uom_id', string='UdM', required=False)
    odometer_init = fields.Float(string='Horómetro inicial')
    odometer_end = fields.Float(string='Horómetro Final')
    cost_odometer = fields.Float(string='Costo Horómetro', compute='compute_total_costo', store=True)
    hrs_maquina = fields.Float(string='Horas Maquina')
    cost_hrs_maquina = fields.Float(string='Costeo Horas Maquina', compute='compute_total_costo', store=True)
    lrts_combustible = fields.Float(string='Litros Combustible')
    cost_lrts_combustible = fields.Float(string='Costeo Litros Combustible')
    regist_cost_id = fields.Many2one(
        comodel_name='real.cost.machinery',
        string="Machinery Reference",
        required=True, ondelete='cascade', index=True, copy=False)

    @api.onchange('machinery_ids','labor_id')
    def onchange_machinery_ids(self):
        if self.machinery_ids:
            odometer = self.env['fleet.vehicle.odometer'].search([('vehicle_id', '=', self.machinery_ids.id)], limit=1)
            if odometer:
                self.odometer_init = odometer.value
        # if self.labor_id:
        #     self.uom_id = self.labor_id.uom_id.id

    # @api.onchange('hrs_maquina')
    # def onchange_hrs_maquina(self):
    #     if self.machinery_ids and self.hrs_maquina:
    #         self.lrts_combustible = 1
        # if self.labor_id:
        #     self.uom_id = self.labor_id.uom_id.id