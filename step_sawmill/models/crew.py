# -*- coding: utf-8 -*-
from odoo import api, fields, models


class StepSawmillCrew(models.Model):
    _name = 'step.sawmill.crew'
    _description = 'Cuadrilla'
    _inherit = ['mail.thread']
    _order = 'date desc, id desc'

    name = fields.Char(string='Descripción', required=True, tracking=True)
    folio = fields.Char(string='Folio')
    date = fields.Date(string='Fecha', default=fields.Date.context_today)
    crew_type = fields.Selection(
        [('own', 'Propio'), ('contractor', 'Contratista')],
        string='Tipo de cuadrilla', default='own', required=True)
    contractor_id = fields.Many2one('res.partner', string='Contratista')
    supervisor_id = fields.Many2one('hr.employee', string='Supervisor')
    time_in = fields.Datetime(string='Hora entrada')
    time_out = fields.Datetime(string='Hora salida')
    member_ids = fields.One2many('step.sawmill.crew.member', 'crew_id', string='Trabajadores')
    headcount = fields.Integer(string='Dotación', compute='_compute_headcount', store=True)
    company_id = fields.Many2one('res.company', string='Empresa',
                                 default=lambda self: self.env.company)
    active = fields.Boolean(default=True)

    @api.depends('member_ids')
    def _compute_headcount(self):
        for rec in self:
            rec.headcount = len(rec.member_ids)


class StepSawmillCrewMember(models.Model):
    _name = 'step.sawmill.crew.member'
    _description = 'Trabajador de cuadrilla'
    _order = 'id'

    crew_id = fields.Many2one('step.sawmill.crew', required=True, ondelete='cascade')
    employee_id = fields.Many2one('hr.employee', string='Trabajador', required=True)
    nip_code = fields.Char(string='Código NIP')
    time_in = fields.Datetime(string='Hora entrada')
    time_out = fields.Datetime(string='Hora salida')
    hours = fields.Float(string='Horas', compute='_compute_hours', store=True)

    @api.depends('time_in', 'time_out')
    def _compute_hours(self):
        for rec in self:
            if rec.time_in and rec.time_out and rec.time_out >= rec.time_in:
                rec.hours = (rec.time_out - rec.time_in).total_seconds() / 3600.0
            else:
                rec.hours = 0.0
