# -*- coding: utf-8 -*-
# Puerto desde Studio (steps_qa) a codigo real - ticket 33 Cerro El Plomo.
from odoo import fields, models


class StepPackingFruitClassTag(models.Model):
    _name = 'step.packing.fruit.class.tag'
    _description = 'Clase de Fruta (etiqueta)'
    _order = 'name'
    _rec_name = 'name'

    name = fields.Char(string='Nombre', required=True)
    color = fields.Integer(string='Color')
