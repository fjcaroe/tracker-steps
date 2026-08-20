# © 2025 (Jamie Escalante <jamie.escalante7@gmail.com>)
# -*- coding: utf-8 -*-

import base64
from odoo import api, fields, models, tools, SUPERUSER_ID, _, Command


class StepCosechaRecepcion(models.Model):
    _name = 'step.cosecha.recepcion'
    _inherit = ['mail.thread']

    name = fields.Char(string='Nombre', index=True, required=True)
    contact_id = fields.Many2one('res.partner', 'Contacto')
    phone = fields.Char(string='Teléfono')
    email = fields.Char(string='Correo electrónico')
    date = fields.Date(string='Fecha')
    dates = fields.Datetime(string='Dates')
    note = fields.Html(string="Notas")
    labor_id = fields.Many2one('product.template', 'Labor/Tarea', required=False)
    responsable_id = fields.Many2one('res.users', 'Responsable')
    company_id = fields.Many2one('res.company', string='Empresa', required=False, default=lambda self: self.env.company)
    recep_line = fields.One2many(
        comodel_name='step.cosecha.recepcion.line',
        inverse_name='recep_id',
        string="Recepcion Lines",
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
