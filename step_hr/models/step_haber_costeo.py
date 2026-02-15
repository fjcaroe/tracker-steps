# © 2025 (Jamie Escalante <jamie.escalante7@gmail.com>)
# -*- coding: utf-8 -*-

import base64
from odoo import api, fields, models, tools, SUPERUSER_ID, _, Command


class StepHaberCosteo(models.Model):
    _name = 'step.haber.costeo'
    _inherit = ['mail.thread']

    name = fields.Char(string='Nombre', index=True, required=True)
    type = fields.Selection(
        selection=[
            ('provi_sueldo', 'Provisión Sueldo'),
            ('provi_seguro', 'Provisión Seguro'),
            ('provi_feriado', 'Provisión Feriado'),
            ('provi_ias', 'Provisión IAS'),
        ],
        string='Tipo',
        required=True,
        readonly=False,
        copy=False,
    )
    debe_account_id = fields.Many2one('account.account', string='Cuenta Debe')
    haber_account_id = fields.Many2one('account.account', string='Cuenta Haber')
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    responsable_id = fields.Many2one("res.users", string="Responsable")
    active = fields.Boolean('Activo')