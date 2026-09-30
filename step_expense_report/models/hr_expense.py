from odoo import fields, models

DOC_TYPES = [
    ("factura", "Factura"),
    ("factura_exenta", "Factura exenta"),
    ("boleta", "Boleta"),
    ("boleta_honorarios", "Boleta de honorarios"),
    ("voucher", "Voucher / comprobante"),
    ("guia", "Guía de despacho"),
    ("otro", "Otro"),
]


class HrExpense(models.Model):
    _inherit = "hr.expense"

    step_doc_type = fields.Selection(DOC_TYPES, string="Tipo doc")
    step_doc_number = fields.Char(string="N° doc")
