# -*- coding: utf-8 -*-
# Puerto desde Studio (steps_qa) a codigo real - ticket 33 Cerro El Plomo.
from odoo import fields, models


class StepExportSaleMode(models.Model):
    _name = 'step.export.sale.mode'
    _description = 'Modalidad de Venta'
    _order = 'sequence, name'
    _rec_name = 'name'

    name = fields.Char(string='Modalidad de Venta', required=True)
    company_id = fields.Many2one('res.company', string='Empresa', default=lambda self: self.env.company)
    sequence = fields.Integer(string='Secuencia', default=10)
    tag_ids = fields.Many2many('step.export.sale.mode.tag', relation='step_export_sale_mode_tag_rel', string='Etiquetas')
    has_price_adjustment = fields.Boolean(string='Ajuste Precio')
    has_customer_claim = fields.Boolean(string='Reclamo Cliente')
