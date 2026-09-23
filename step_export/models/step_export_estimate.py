# -*- coding: utf-8 -*-
# Puerto desde Studio (steps_qa) a codigo real - ticket 33 Cerro El Plomo.
from odoo import fields, models


class StepExportEstimate(models.Model):
    _name = 'step.export.estimate'
    _description = 'Estimación de Cosecha'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'sequence, id'
    _rec_name = 'name'

    name = fields.Char(string='Descripción', required=True)
    user_id = fields.Many2one('res.users', string='Responsable')
    company_id = fields.Many2one('res.company', string='Empresa', default=lambda self: self.env.company)
    notes = fields.Html(string='Notas')
    date = fields.Date(string='Fecha')
    date_start = fields.Datetime(string='Fecha de inicio')
    date_stop = fields.Datetime(string='Fecha de finalización')
    image = fields.Binary(string='Imagen')
    sequence = fields.Integer(string='Secuencia', default=10)
    stage_id = fields.Many2one('step.export.estimate.stage', string='Etapa', required=True, group_expand='_read_group_stage_ids', tracking=True)
    priority = fields.Boolean(string='Alta prioridad')
    color = fields.Integer(string='Color')
    tag_ids = fields.Many2many('step.export.estimate.tag', string='Etiquetas')
    fundo_id = fields.Many2one('step.fundo', string='Fundo')
    sector_id = fields.Many2one('res.sector', string='Sector')
    species_id = fields.Many2one('step.especie', string='Especie')
    variety_group_id = fields.Many2one('step.grupo.variedad', string='Grupo Variedad')
    variety_id = fields.Many2one('step.variedad', string='Variedad')
    cost_center_id = fields.Many2one('step.management.cost.center', string='Centro de Costos')
    season_id = fields.Many2one('step.temporada', string='Temporada')
    approved_by_id = fields.Many2one('hr.employee', string='Autoriza')
    estimate_version = fields.Char(string='Versión estimación')
    yield_kg = fields.Float(string='Kg Rendimiento')

    def _read_group_stage_ids(self, stages, domain):
        return self.env['step.export.estimate.stage'].search([], order='sequence, id')

