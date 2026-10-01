# -*- coding: utf-8 -*-
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    treasury_batch_approval_threshold = fields.Monetary(
        string="Tope por lote",
        currency_field="currency_id",
        help="Monto a partir del cual un lote de pago saliente requiere "
             "aprobación adicional antes de exportarse al banco. En cero, "
             "no se exige aprobación.",
    )
    treasury_batch_approver_id = fields.Many2one(
        "res.users", string="Aprobador de tope",
        help="Usuario que debe aprobar un lote de pago saliente cuando su "
             "monto supera el tope configurado.",
    )
