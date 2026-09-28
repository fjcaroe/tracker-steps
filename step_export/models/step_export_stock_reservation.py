# -*- coding: utf-8 -*-
# Puerto desde Studio (steps_qa) a codigo real - ticket 33 Cerro El Plomo.
from odoo import fields, models


class StepExportStockReservation(models.Model):
    _name = 'step.export.stock.reservation'
    _description = 'Reserva de Stock'
    _order = 'sequence, name'
    _rec_name = 'name'

    name = fields.Char(string='Reserva de Stock', required=True)
    company_id = fields.Many2one('res.company', string='Empresa', default=lambda self: self.env.company)
    sequence = fields.Integer(string='Secuencia', default=10)
    user_id = fields.Many2one('res.users', string='Responsable')
