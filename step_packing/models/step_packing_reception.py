# -*- coding: utf-8 -*-
# Puerto desde Studio (steps_qa) a codigo real - ticket 33 Cerro El Plomo.
from odoo import fields, models


class StepPackingReception(models.Model):
    _name = 'step.packing.reception'
    _description = 'Recepción a Granel'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'sequence, id'
    _rec_name = 'name'

    name = fields.Char(string='Descripción', required=True)
    user_id = fields.Many2one('res.users', string='Responsable')
    partner_id = fields.Many2one('res.partner', string='Contacto')
    partner_phone = fields.Char(related='partner_id.phone', string='Teléfono', store=False)
    partner_email = fields.Char(related='partner_id.email', string='Correo electrónico', store=False)
    company_id = fields.Many2one('res.company', string='Empresa', default=lambda self: self.env.company)
    notes = fields.Html(string='Notas')
    date = fields.Date(string='Fecha')
    date_start = fields.Datetime(string='Fecha de inicio')
    date_stop = fields.Datetime(string='Fecha de finalización')
    sequence = fields.Integer(string='Secuencia', default=10)
    stage_id = fields.Many2one('step.packing.reception.stage', string='Etapa', required=True, group_expand='_read_group_stage_ids', tracking=True)
    priority = fields.Boolean(string='Alta prioridad')
    color = fields.Integer(string='Color')
    tag_ids = fields.Many2many('step.packing.reception.tag', string='Etiquetas')
    image = fields.Binary(string='Imagen')

    def _read_group_stage_ids(self, stages, domain):
        return self.env['step.packing.reception.stage'].search([], order='sequence, id')

