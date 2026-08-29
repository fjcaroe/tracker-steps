# © 2025 (Jamie Escalante <jamie.escalante7@gmail.com>)
# -*- coding: utf-8 -*-

from odoo import api, models, fields

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    step_journal_machinery = fields.Many2one('account.journal', string="Diario Maquinaria", related='company_id.step_journal_machinery',
                                      required=False, readonly=False)

