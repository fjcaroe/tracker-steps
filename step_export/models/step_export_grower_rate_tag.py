# -*- coding: utf-8 -*-
# Puerto desde Studio (steps_qa) a codigo real - ticket 33 Cerro El Plomo.
from odoo import fields, models


class StepExportGrowerRateTag(models.Model):
    _name = 'step.export.grower.rate.tag'
    _description = 'Tarifa Productor (etiqueta)'
    _order = 'name'
    _rec_name = 'name'

    name = fields.Char(string='Nombre', required=True)
    color = fields.Integer(string='Color')
