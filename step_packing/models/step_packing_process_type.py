# -*- coding: utf-8 -*-
# Puerto desde Studio (steps_qa) a codigo real - ticket 33 Cerro El Plomo.
from odoo import fields, models


class StepPackingProcessType(models.Model):
    _name = 'step.packing.process.type'
    _description = 'Tipo de Proceso'
    _order = 'sequence, name'
    _rec_name = 'name'

    name = fields.Char(string='Tipo de Proceso', required=True)
    company_id = fields.Many2one('res.company', string='Empresa', default=lambda self: self.env.company)
    sequence = fields.Integer(string='Secuencia', default=10)
    tag_ids = fields.Many2many('step.packing.process.type.tag', relation='step_packing_process_type_tag_rel', string='Etiquetas')
