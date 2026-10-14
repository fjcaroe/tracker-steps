# -*- coding: utf-8 -*-
# Puerto desde Studio (steps_qa) a codigo real - ticket 33 Cerro El Plomo.
from odoo import fields, models


class StepPackingTagType(models.Model):
    _name = 'step.packing.tag.type'
    _description = 'Tipo de Tarja'
    _order = 'sequence, name'
    _rec_name = 'name'

    name = fields.Char(string='Tipo de Tarja', required=True)
    company_id = fields.Many2one('res.company', string='Empresa', default=lambda self: self.env.company)
    sequence = fields.Integer(string='Secuencia', default=10)
    tag_ids = fields.Many2many('step.packing.tag.type.tag', relation='step_packing_tag_type_tag_rel', string='Etiquetas')
    code = fields.Char(string='Sigla Tarja')
