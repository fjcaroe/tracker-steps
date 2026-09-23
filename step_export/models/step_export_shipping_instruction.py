# -*- coding: utf-8 -*-
# Puerto desde Studio (steps_qa) a codigo real - ticket 33 Cerro El Plomo.
from odoo import fields, models


class StepExportShippingInstruction(models.Model):
    _name = 'step.export.shipping.instruction'
    _description = 'Instructivo de Embarque'
    _order = 'sequence, name'
    _rec_name = 'name'

    name = fields.Char(string='Instructivo de Embarque', required=True)
    company_id = fields.Many2one('res.company', string='Empresa', default=lambda self: self.env.company)
    sequence = fields.Integer(string='Secuencia', default=10)
    tag_ids = fields.Many2many('step.export.shipping.instruction.tag', relation='step_export_shipping_instruction_tag_rel', string='Etiquetas')
    user_id = fields.Many2one('res.users', string='Responsable')
    partner_id = fields.Many2one('res.partner', string='Contacto')
    notes = fields.Html(string='Notas')
    date = fields.Date(string='Fecha')
    date_start = fields.Datetime(string='Fecha de inicio')
    date_stop = fields.Datetime(string='Fecha de finalización')
