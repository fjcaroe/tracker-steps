# -*- coding: utf-8 -*-
# Puerto desde Studio (steps_qa) a codigo real - ticket 33 Cerro El Plomo.
from odoo import fields, models


class StepExportDispatchOrder(models.Model):
    _name = 'step.export.dispatch.order'
    _description = 'Orden de Despacho'
    _order = 'sequence, name'
    _rec_name = 'name'

    name = fields.Char(string='Orden de Despacho', required=True)
    company_id = fields.Many2one('res.company', string='Empresa', default=lambda self: self.env.company)
    sequence = fields.Integer(string='Secuencia', default=10)
    user_id = fields.Many2one('res.users', string='Responsable')
