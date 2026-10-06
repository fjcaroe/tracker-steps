# -*- coding: utf-8 -*-
from odoo import api, fields, models


class StepSawmillSawing(models.Model):
    _name = 'step.sawmill.sawing'
    _description = 'Aserrío'
    _inherit = ['step.sawmill.process.mixin', 'mail.thread', 'mail.activity.mixin']
    _sequence_code = 'step.sawmill.sawing'

    raw_product_id = fields.Many2one('product.product', string='Materia prima')
    raw_quantity = fields.Float(string='Cantidad MP')
    raw_uom_id = fields.Many2one('uom.uom', string='UdM')
    tarjas = fields.Char(string='Tarjas')
    output_ids = fields.One2many('step.sawmill.output.line', 'sawing_id', string='Productos obtenidos')
    input_ids = fields.One2many('step.sawmill.input.line', 'sawing_id', string='Materia prima consumida')
    cost_ids = fields.One2many('step.sawmill.cost.line', 'sawing_id', string='Valorización')

    @api.onchange('raw_product_id')
    def _onchange_raw_product_id(self):
        if self.raw_product_id:
            self.raw_uom_id = self.raw_product_id.uom_id
