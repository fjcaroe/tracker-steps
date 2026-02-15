# © 2025 (Jamie Escalante <jamie.escalante7@gmail.com>)
# -*- coding: utf-8 -*-

from odoo import api, Command, fields, models, _

class StepTracker(models.Model):
    _name = 'step.tracker'
    _inherit = ['mail.thread']

    name = fields.Char(string='Nombre', index=True, required=True)
    company_id = fields.Many2one('res.company', string='Empresa', required=False, default=lambda self: self.env.company)
    note = fields.Html(string="Notas")