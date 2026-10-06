# -*- coding: utf-8 -*-
# Puerto desde Studio (steps_qa) a codigo real - ticket 33 Cerro El Plomo.
from odoo import fields, models


class StepExportGrowerRate(models.Model):
    _name = 'step.export.grower.rate'
    _description = 'Tarifa Productor'
    _order = 'sequence, name'
    _rec_name = 'name'

    name = fields.Char(string='Tarifa Productor', required=True)
    company_id = fields.Many2one('res.company', string='Empresa', default=lambda self: self.env.company)
    sequence = fields.Integer(string='Secuencia', default=10)
    tag_ids = fields.Many2many('step.export.grower.rate.tag', relation='step_export_grower_rate_tag_rel', string='Etiquetas')
    notes = fields.Html(string='Notas')
    date = fields.Date(string='Fecha')
    season_id = fields.Many2one('step.temporada', string='Temporada')
    species_id = fields.Many2one('step.especie', string='Especie')
    discount_item_id = fields.Many2one('step.export.grower.discount', string='Ítem Productor')
