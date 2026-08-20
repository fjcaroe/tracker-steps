# © 2025 (Jamie Escalante <jamie.escalante7@gmail.com>)
# -*- coding: utf-8 -*-

import base64
from odoo import api, fields, models, tools, SUPERUSER_ID, _, Command


class StepCosechaProceso(models.Model):
    _name = 'step.cosecha.proceso'
    _inherit = ['mail.thread']

    name = fields.Char(string='Nombre', index=True, required=True)
    date = fields.Date(string='Fecha')
    super_id = fields.Many2one('hr.employee', 'Supervisor')
    cosecha_ubi_id = fields.Many2one('step.cosecha.ubicacion', 'Tipo Ubicación')
    responsable_id = fields.Many2one('res.users', 'Responsable')
    company_id = fields.Many2one('res.company', string='Empresa', required=False, default=lambda self: self.env.company)
    proceso_line = fields.One2many(
        comodel_name='step.cosecha.proceso.line',
        inverse_name='proceso_id',
        string="Proceso Lines",
        copy=True, auto_join=True)
    state = fields.Selection(
        selection=[
            ('draft', 'Nuevo'),
            ('progress', 'En progreso'),
            ('done', 'Listo'),
        ],
        string='Estado',
        required=True,
        readonly=False,
        copy=False,
        default='draft',
    )

    def action_draft(self):
        for movi in self:
            movi.write({'state': 'draft'})

    def action_progress(self):
        for movi in self:
            movi.write({'state': 'progress'})

    def action_done(self):
        for movi in self:
            movi.write({'state': 'done'})
