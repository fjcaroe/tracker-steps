# -*- coding: utf-8 -*-

from odoo import fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    step_trans_person = fields.Boolean('¿Transporte de personal?')
    step_chofer = fields.Boolean(string='¿Chofer?')
    transpor_id = fields.Many2one('res.partner', 'Transportista')
