# -*- coding: utf-8 -*-
# Puerto desde Studio (steps_qa) a codigo real - ticket 33 Cerro El Plomo.
from odoo import fields, models


class StepPackingLine(models.Model):
    _name = 'step.packing.line'
    _description = 'Línea de Proceso'
    _order = 'sequence, name'
    _rec_name = 'name'

    name = fields.Char(string='Línea de Proceso', required=True)
    company_id = fields.Many2one('res.company', string='Empresa', default=lambda self: self.env.company)
    sequence = fields.Integer(string='Secuencia', default=10)
    tag_ids = fields.Many2many('step.packing.line.tag', relation='step_packing_line_tag_rel', string='Etiquetas')
    staff_total = fields.Integer(string='Dotación Total')
    containers_per_hour = fields.Integer(string='Envases x hora')
    kg_per_hour = fields.Integer(string='Kilos x hora')
    species_id = fields.Many2one('step.especie', string='Especie Línea')
    package_id = fields.Many2one('product.packaging', string='Envase referencia')
    workcenter_id = fields.Many2one('mrp.workcenter', string='Centro de trabajo')
    capacity_inches = fields.Float(string='Capacidad pulgadas')
    capacity_m3 = fields.Float(string='Capacidad m3')
