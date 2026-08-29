# © 2025 (Jamie Escalante <jamie.escalante7@gmail.com>)
# -*- coding: utf-8 -*-

from odoo import fields, models, api
from odoo.tools import frozendict


class AccountMove(models.Model):
    _inherit = 'account.move'

    # state = fields.Selection(
    #     selection_add=[
    #         ('pro', 'PRO-FORMA')
    #     ],
    #     ondelete={
    #         'pro': 'cascade'
    #     },
    # )
    propio = fields.Boolean(string='Propio')
    contra = fields.Boolean(string='Contratista')
    cosecha = fields.Boolean(string='Cosecha')
