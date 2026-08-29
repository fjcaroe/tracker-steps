# -*- coding: utf-8 -*-
"""Fecha prevista de pago en la orden de compra."""

from odoo import fields, models


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    treasury_due_date = fields.Date(
        string="Vencimiento (Tesorería)",
        help="Fecha prevista de pago usada por el flujo de caja. "
             "Si se deja vacía se usa la fecha planificada o la del pedido.",
    )

    def _treasury_due_date(self):
        self.ensure_one()
        if self.treasury_due_date:
            return self.treasury_due_date
        if self.date_planned:
            return fields.Date.to_date(self.date_planned)
        return fields.Date.to_date(self.date_order)
