# © 2025 (Jamie Escalante <jamie.escalante7@gmail.com>)
# -*- coding: utf-8 -*-

from odoo import api, models, fields

class ResCompany(models.Model):
    _inherit = "res.company"

    step_journal_machinery = fields.Many2one('account.journal', string="Diario Maquinaria")