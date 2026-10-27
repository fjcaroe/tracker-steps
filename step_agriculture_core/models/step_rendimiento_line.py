# © 2025 (Jamie Escalante <jamie.escalante7@gmail.com>)
# -*- coding: utf-8 -*-

from odoo import api, Command, fields, models, _

class StepRendimientoLines(models.Model):
    _name = 'step.rendimiento.line'
    _inherit = ['mail.thread']

    name = fields.Char(string='Descripcion', index=True, required=True)
    centro_id = fields.Many2one(
        comodel_name='account.analytic.account',
        string="Centro costo Reference",
        required=True, ondelete='cascade', index=True, copy=False)
    labor_id = fields.Many2one('product.template', 'Labor/Tarea', required=True)
    uom_id = fields.Many2one('uom.uom', 'UdM', required=True)
    uom_trato = fields.Many2one('uom.uom', 'Relación Trato', required=True)
    redim_std = fields.Float(string='Redim. Standar')