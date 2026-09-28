# -*- coding: utf-8 -*-
# Puerto desde Studio (steps_qa) a codigo real - ticket 33 Cerro El Plomo.
from odoo import fields, models


class StepPackingReceptionStage(models.Model):
    _name = 'step.packing.reception.stage'
    _description = 'Recepción a Granel (etapa)'
    _order = 'sequence, id'
    _rec_name = 'name'

    name = fields.Char(string='Nombre de la etapa', required=True)
    sequence = fields.Integer(string='Secuencia', default=10)
