# -*- coding: utf-8 -*-
"""Fecha prevista de cobro en la nota de venta.

Campo técnico propio (`treasury_due_date`), no `x_studio_*`, tal como exige el
encargo. Si no se informa, se usa la fecha comprometida y, en su defecto, la
fecha del pedido.
"""

from odoo import fields, models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    treasury_due_date = fields.Date(
        string="Vencimiento (Tesorería)",
        help="Fecha prevista de cobro usada por el flujo de caja. "
             "Si se deja vacía se usa la fecha comprometida o la del pedido.",
    )

    def _treasury_due_date(self):
        self.ensure_one()
        if self.treasury_due_date:
            return self.treasury_due_date
        if self.commitment_date:
            return fields.Date.to_date(self.commitment_date)
        return fields.Date.to_date(self.date_order)
