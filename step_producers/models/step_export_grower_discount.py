# -*- coding: utf-8 -*-
# Puerto desde Studio (steps_qa) a codigo real - ticket 33 Cerro El Plomo.
from odoo import fields, models


class StepExportGrowerDiscount(models.Model):
    _name = 'step.export.grower.discount'
    _description = 'Ítem Productor (Descuento Liquidación)'
    _order = 'sequence, name'
    _rec_name = 'name'

    name = fields.Char(string='Ítem Productor (Descuento Liquidación)', required=True)
    company_id = fields.Many2one('res.company', string='Empresa', default=lambda self: self.env.company)
    sequence = fields.Integer(string='Secuencia', default=10)
    tag_ids = fields.Many2many('step.export.grower.discount.tag', relation='step_export_grower_discount_tag_rel', string='Etiquetas')
    code = fields.Char(string='Código Ítem Productor')
    account_id = fields.Many2one('account.account', string='Cuenta Contable')
