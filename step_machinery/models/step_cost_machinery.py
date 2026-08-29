# © 2025 (Jamie Escalante <jamie.escalante7@gmail.com>)
# -*- coding: utf-8 -*-

import base64
from odoo import api, fields, models, tools, SUPERUSER_ID, _, Command


class StepCostMachinery(models.Model):
    _name = 'step.cost.machinery'
    _inherit = ['mail.thread']

    name = fields.Char(string='Nombre', index=True, required=True)
    date = fields.Date(string='Fecha')
    fundo_id = fields.Many2one('step.fundo',
                               string="Fundo",
                               required=True, ondelete='cascade', copy=False)
    responsable_id = fields.Many2one("hr.employee", string="Responsable")
    user_id = fields.Many2one('hr.employee', string='Autoriza', tracking=True)
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    # total = fields.Monetary("Valor total", store=True)
    note = fields.Html("Notas")



