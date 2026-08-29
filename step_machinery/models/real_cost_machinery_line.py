# © 2025 (Jamie Escalante <jamie.escalante7@gmail.com>)
# -*- coding: utf-8 -*-

import base64
from odoo import api, fields, models, tools, SUPERUSER_ID, _, Command


class RealCostMachineryLine(models.Model):
    _name = 'real.cost.machinery.line'
    _inherit = ["analytic.mixin"]

    # @api.depends('hrs_maquina','odometer_end','odometer_end')
    # def compute_total_costo(self):
    #     eta_list = []
    #     hora_extra = 0
    #     for move in self:
    #
    #         move.cost_hrs_maquina = float(move.hrs_maquina) * float(move.machinery_ids.step_cost_hrs)
    #         move.cost_odometer = float(move.odometer_end) - float(move.odometer_init)

    def _inverse_analytic_distribution(self):
        """If analytic distribution is set on move, write it on all move lines"""
        for move in self:
            move.write(
                {"analytic_distribution": move.analytic_distribution}
            )

    name = fields.Char(string='Nombre Ref', index=True, required=False)
    date = fields.Date(string='Fecha')
    machinery_ids = fields.Many2one(
        comodel_name='fleet.vehicle',
        string="Maquinaria",
        required=False, ondelete='cascade', index=True, copy=False)
    account_id = fields.Many2one('account.account', string='Cuenta')
    implement_id = fields.Many2one(
        comodel_name='step.machinery.implement',
        string="Implemento",
        required=False, ondelete='cascade', index=True, copy=False)
    employee_id = fields.Many2one('hr.employee', 'Conductor')
    labor_id = fields.Many2one('step.labor', 'Labor', required=False)
    actividad_id = fields.Many2one(related='labor_id.actividad_id', string='Actividad',
                                   )
    uom_id = fields.Many2one(related='labor_id.uom_id', string='UdM', required=False)
    odometer_init = fields.Float(string='Horómetro inicial')
    odometer_end = fields.Float(string='Horómetro Final')
    hrs_maquina = fields.Float(string='Horas Maquina')
    lrts_combustible = fields.Float(string='Litros Combustible')
    cost_lrts_combustible = fields.Float(string='Costeo Litros Combustible')
    real_cost_id = fields.Many2one(
        comodel_name='real.cost.machinery',
        string="Machinery Reference",
        required=True, ondelete='cascade', index=True, copy=False)
    analytic_distribution = fields.Json( string='Distribución Analítica'
    )
    monto = fields.Float('Monto')

    @api.onchange('hrs_maquina')
    def onchange_hrs_maquina(self):
        if self.machinery_ids and self.hrs_maquina:
            self.lrts_combustible = 1
        # if self.labor_id:
        #     self.uom_id = self.labor_id.uom_id.id