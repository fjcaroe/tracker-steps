# -*- coding: utf-8 -*-
# Puerto desde Studio (steps_qa) a codigo real - ticket 33 Cerro El Plomo.
from odoo import fields, models


class StepPackingStopReason(models.Model):
    _name = 'step.packing.stop.reason'
    _description = 'Causa de Detención de Línea'
    _order = 'sequence, name'
    _rec_name = 'name'

    name = fields.Char(string='Causa de Detención de Línea', required=True)
    company_id = fields.Many2one('res.company', string='Empresa', default=lambda self: self.env.company)
    sequence = fields.Integer(string='Secuencia', default=10)
    tag_ids = fields.Many2many('step.packing.stop.reason.tag', relation='step_packing_stop_reason_tag_rel', string='Etiquetas')
