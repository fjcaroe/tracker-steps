# © 2026 Steps
# -*- coding: utf-8 -*-

from odoo import fields, models


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    harvest_registry_id = fields.Many2one(
        'step.cosecha.registry', string='Registro de cosecha',
        copy=False, index=True, ondelete='set null'
    )

    def write(self, vals):
        result = super().write(vals)
        if 'state' in vals:
            for picking in self.filtered('harvest_registry_id'):
                picking.harvest_registry_id.cos_recibida = picking.state == 'done'
        return result
