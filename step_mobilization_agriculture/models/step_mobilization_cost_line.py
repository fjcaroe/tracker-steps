# -*- coding: utf-8 -*-

from odoo import fields, models


class StepMoviCostLine(models.Model):
    _inherit = 'step.movi.cost.line'

    fundo_id = fields.Many2one(related='movi_id.fundo_id', string="Fundo", store=True)

    def _get_extra_analytic_account_ids(self):
        self.ensure_one()
        account_ids = super()._get_extra_analytic_account_ids()
        if self.labor_id and self.labor_id.actividad_id:
            account_ids.append(self.labor_id.actividad_id.id)
        return account_ids
