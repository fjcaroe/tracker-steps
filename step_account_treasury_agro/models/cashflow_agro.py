# -*- coding: utf-8 -*-
"""Fundo opcional en el flujo de caja."""

from odoo import fields, models


class StepCashflowAgro(models.Model):
    _inherit = "step.cashflow"

    fundo_id = fields.Many2one(
        "step.fundo", string="Fundo", ondelete="restrict", tracking=True,
        help="Unidad agrícola a la que se asocia la planificación, si aplica.",
    )
