# © 2025 (Jamie Escalante <jamie.escalante7@gmail.com>)
# -*- coding: utf-8 -*-

import base64
from odoo import api, fields, models, tools, SUPERUSER_ID, _, Command


class StepMachineryImplement(models.Model):
    _name = 'step.machinery.implement'
    _inherit = ['mail.thread']

    name = fields.Char(string='Nombre', index=True, required=True)
    cod = fields.Char(string='Código')
    type_imp = fields.Selection(string='Tipo Implemento',
                                selection=[('manual', 'Manual'),
                                           ('tiro', 'De Tiro')])
    is_bpa = fields.Boolean(string='Uso BPA')
    cap_ltr = fields.Char(string='Capacidad Litros')
    cap_kg = fields.Char(string='Capacidad Kilos')
    fundo_id = fields.Many2one('step.fundo',
                               string="Fundo",
                               required=True, ondelete='cascade', copy=False)
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    responsable_id = fields.Many2one("hr.employee", string="Responsable")