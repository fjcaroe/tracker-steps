# © 2026 Steps
# -*- coding: utf-8 -*-

from odoo import fields, models


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    cosecha = fields.Boolean('Es Cosecha')

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

    def _sync_harvest_receipt_state(self):
        # Only an operator transition updates the linked receipt. Never schedule
        # a historical/global recompute while adopting the existing Boolean.
        for picking in self.filtered('harvest_registry_id'):
            registry=picking.harvest_registry_id
            if registry.reception_picking_id == picking:
                registry.cos_recibida = picking.state == 'done'

    def _action_done(self):
        result=super()._action_done()
        self._sync_harvest_receipt_state()
        return result

    def action_cancel(self):
        result=super().action_cancel()
        self._sync_harvest_receipt_state()
        return result
