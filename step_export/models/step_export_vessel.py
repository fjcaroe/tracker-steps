# -*- coding: utf-8 -*-
# Puerto desde Studio (steps_qa) a codigo real - ticket 33 Cerro El Plomo.
from odoo import fields, models


class StepExportVessel(models.Model):
    _name = 'step.export.vessel'
    _description = 'Nave'
    _order = 'sequence, name'
    _rec_name = 'name'

    name = fields.Char(string='Nave', required=True)
    company_id = fields.Many2one('res.company', string='Empresa', default=lambda self: self.env.company)
    sequence = fields.Integer(string='Secuencia', default=10)
    tag_ids = fields.Many2many('step.export.vessel.tag', relation='step_export_vessel_tag_rel', string='Etiquetas')
    carrier_id = fields.Many2one('res.partner', string='Naviera')
    code = fields.Char(string='Código Nave')
