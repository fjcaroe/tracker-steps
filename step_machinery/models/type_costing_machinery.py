# © 2025 (Jamie Escalante <jamie.escalante7@gmail.com>)
# -*- coding: utf-8 -*-

import base64
from odoo import api, fields, models, tools, SUPERUSER_ID, _, Command


class TypeCostingMachinery(models.Model):
    _name = 'type.costing.machinery'
    _inherit = ['mail.thread']

    name = fields.Char(string='Nombre', index=True, required=True)
    type = fields.Selection(string='Tipo',
                                  selection=[('real', 'Real'),
                                             ('std', 'Estándar')], default='real')
    cod = fields.Char(string='Código Costeo')
    comment = fields.Html(string='Comentario')
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    aplica = fields.Boolean(string='Aplica costeo')
    responsable_id = fields.Many2one(
        "res.users",
        string="Responsable",
        default=lambda self: self.env.user,
        help="Usuario responsable del costeo.",
    )
