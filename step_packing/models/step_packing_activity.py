# -*- coding: utf-8 -*-
# Puerto desde Studio (steps_qa) a codigo real - ticket 33 Cerro El Plomo.
from odoo import fields, models


class StepPackingActivity(models.Model):
    _name = 'step.packing.activity'
    _description = 'Actividad Agrícola'
    _order = 'sequence, name'
    _rec_name = 'name'

    name = fields.Char(string='Actividad Agrícola', required=True)
    company_id = fields.Many2one('res.company', string='Empresa', default=lambda self: self.env.company)
    sequence = fields.Integer(string='Secuencia', default=10)
    tag_ids = fields.Many2many('step.packing.activity.tag', relation='step_packing_activity_tag_rel', string='Etiquetas')
    code = fields.Char(string='Código Actividad')
    date = fields.Date(string='Fecha')
    notes = fields.Html(string='Notas')
