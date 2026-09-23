# -*- coding: utf-8 -*-
# Puerto desde Studio (steps_qa) a codigo real - ticket 33 Cerro El Plomo.
from odoo import fields, models


class StepPackingFruitCaliber(models.Model):
    _name = 'step.packing.fruit.caliber'
    _description = 'Calibre de Fruta'
    _order = 'sequence, name'
    _rec_name = 'name'

    name = fields.Char(string='Calibre de Fruta', required=True)
    company_id = fields.Many2one('res.company', string='Empresa', default=lambda self: self.env.company)
    sequence = fields.Integer(string='Secuencia', default=10)
    tag_ids = fields.Many2many('step.packing.fruit.caliber.tag', relation='step_packing_fruit_caliber_tag_rel', string='Etiquetas')
    caliber_name = fields.Char(string='Nombre Calibre')
    caliber_range = fields.Char(string='Rango Calibre')
    species_id = fields.Many2one('step.especie', string='Especie')
    fruit_weight_gr = fields.Integer(string='Peso Fruto (grs)')
    weight_range = fields.Char(string='Rango peso (grs)')
    units_per_kg = fields.Integer(string='Frutos x Kg')
    caliber_group_id = fields.Many2one('step.packing.caliber.group', string='Grupo de calibre')
