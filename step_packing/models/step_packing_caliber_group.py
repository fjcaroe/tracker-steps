# -*- coding: utf-8 -*-
# Puerto desde Studio (steps_qa) a codigo real - ticket 33 Cerro El Plomo.
from odoo import fields, models


class StepPackingCaliberGroup(models.Model):
    _name = 'step.packing.caliber.group'
    _description = 'Grupo de Calibre'
    _order = 'sequence, name'
    _rec_name = 'name'

    name = fields.Char(string='Grupo de Calibre', required=True)
    company_id = fields.Many2one('res.company', string='Empresa', default=lambda self: self.env.company)
    sequence = fields.Integer(string='Secuencia', default=10)
    tag_ids = fields.Many2many('step.packing.caliber.group.tag', relation='step_packing_caliber_group_tag_rel', string='Etiquetas')
    caliber_range = fields.Char(string='Rango Calibre')
    weight_range = fields.Char(string='Rango peso (grs)')
    species_id = fields.Many2one('step.especie', string='Especie')
