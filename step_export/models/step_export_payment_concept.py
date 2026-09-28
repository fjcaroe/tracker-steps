# -*- coding: utf-8 -*-
# Puerto desde Studio (steps_qa) a codigo real - ticket 33 Cerro El Plomo.
from odoo import fields, models


class StepExportPaymentConcept(models.Model):
    _name = 'step.export.payment.concept'
    _description = 'Concepto de Pago Productor'
    _order = 'sequence, name'
    _rec_name = 'name'

    name = fields.Char(string='Concepto de Pago Productor', required=True)
    company_id = fields.Many2one('res.company', string='Empresa', default=lambda self: self.env.company)
    sequence = fields.Integer(string='Secuencia', default=10)
    code = fields.Char(string='Código')
    notes = fields.Html(string='Notas')
    date = fields.Date(string='Fecha')
