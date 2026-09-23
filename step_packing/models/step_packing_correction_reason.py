# -*- coding: utf-8 -*-
# Puerto desde Studio (steps_qa) a codigo real - ticket 33 Cerro El Plomo.
from odoo import fields, models


class StepPackingCorrectionReason(models.Model):
    _name = 'step.packing.correction.reason'
    _description = 'Causa Corrección de Proceso'
    _order = 'sequence, name'
    _rec_name = 'name'

    name = fields.Char(string='Causa Corrección de Proceso', required=True)
    company_id = fields.Many2one('res.company', string='Empresa', default=lambda self: self.env.company)
    sequence = fields.Integer(string='Secuencia', default=10)
    tag_ids = fields.Many2many('step.packing.correction.reason.tag', relation='step_packing_correction_reason_tag_rel', string='Etiquetas')
    process_type_id = fields.Many2one('step.packing.process.type', string='Tipo Proceso')
