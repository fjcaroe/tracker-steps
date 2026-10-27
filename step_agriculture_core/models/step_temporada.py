# © 2025 (Jamie Escalante <jamie.escalante7@gmail.com>)
# -*- coding: utf-8 -*-

from odoo import api, Command, fields, models, _

class StepTemporada(models.Model):
    _name = 'step.temporada'
    _inherit = ['mail.thread']

    name = fields.Char(string='Nombre', index=True, required=True)
    code = fields.Char(string='Código Temp.')
    start_date = fields.Date(string='Fecha Inicio')
    end_date = fields.Date(string='Fecha Término')
    company_id = fields.Many2one('res.company', string='Empresa', required=True, default=lambda self: self.env.company)
    cost_id = fields.Many2one(
        'account.analytic.account', "Cuenta analítica",
        )
    plan_id = fields.Many2one(
        'account.analytic.plan', "Plan Analítico",
        )
    # route_line = fields.One2many(
    #     comodel_name='hr.route.line',
    #     inverse_name='route_id',
    #     string="Route Lines",
    #     copy=True, auto_join=True)