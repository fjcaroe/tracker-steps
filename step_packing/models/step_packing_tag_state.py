# -*- coding: utf-8 -*-
# Puerto desde Studio (steps_qa) a codigo real - ticket 33 Cerro El Plomo.
from odoo import fields, models


class StepPackingTagState(models.Model):
    _name = 'step.packing.tag.state'
    _description = 'Estado de Tarja'
    _order = 'sequence, name'
    _rec_name = 'name'

    name = fields.Char(string='Estado de Tarja', required=True)
    company_id = fields.Many2one('res.company', string='Empresa', default=lambda self: self.env.company)
    sequence = fields.Integer(string='Secuencia', default=10)
    tag_ids = fields.Many2many('step.packing.tag.state.tag', relation='step_packing_tag_state_tag_rel', string='Etiquetas')
    code = fields.Char(string='Sigla Estado Tarja')
