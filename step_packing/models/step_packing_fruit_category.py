# -*- coding: utf-8 -*-
# Puerto desde Studio (steps_qa) a codigo real - ticket 33 Cerro El Plomo.
from odoo import fields, models


class StepPackingFruitCategory(models.Model):
    _name = 'step.packing.fruit.category'
    _description = 'Categoría de Fruta'
    _order = 'sequence, name'
    _rec_name = 'name'

    name = fields.Char(string='Categoría de Fruta', required=True)
    company_id = fields.Many2one('res.company', string='Empresa', default=lambda self: self.env.company)
    sequence = fields.Integer(string='Secuencia', default=10)
    tag_ids = fields.Many2many('step.packing.fruit.category.tag', relation='step_packing_fruit_category_tag_rel', string='Etiquetas')
