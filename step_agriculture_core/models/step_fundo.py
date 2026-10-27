# © 2025 (Jamie Escalante <jamie.escalante7@gmail.com>)
# -*- coding: utf-8 -*-

from odoo import api, Command, fields, models, _

class StepFundo(models.Model):
    _name = 'step.fundo'
    _inherit = ['mail.thread']

    name = fields.Char(string='Nombre', index=True, required=True)
    street = fields.Char(string='Street')
    street2 = fields.Char(string='Street2')
    city_id = fields.Char(string='City ID')
    city = fields.Char(string='City')
    state_id = fields.Char(string='State')
    zip_code = fields.Char(string='ZIP')
    partner_id = fields.Many2one('res.partner', 'Productor')
    country_id = fields.Many2one('res.country', related='partner_id.country_id', string="Country")
    date = fields.Date(string='Fecha')
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    fundo_code = fields.Char(string='Código Fundo')
    csg_code = fields.Char(string='Código CSG')
    sdp_code = fields.Char(string='Código SDP')
    ggn_code = fields.Char(string='Código GGN')
    hec_total = fields.Integer(string='Hectáreas Totales')
    hec_disp = fields.Integer(string='Hectáreas Disponibles')
    hec_plant = fields.Integer(string='Hectáreas Plantadas')
    hec_otro = fields.Integer(string='Hectáreas otros usos')
    sector_id = fields.Many2one('res.sector', copy=False, tracking=True,
                                string='Sector')
    schedule_id = fields.Many2one('step.work.schedule', copy=False, tracking=True,
                                          string='Horario de trabajo')
    # route_line = fields.One2many(
    #     comodel_name='hr.route.line',
    #     inverse_name='route_id',
    #     string="Route Lines",
    #     copy=True, auto_join=True)