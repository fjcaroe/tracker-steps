# -*- coding: utf-8 -*-
# Puerto desde Studio (steps_qa) a codigo real - ticket 33 Cerro El Plomo.
from odoo import fields, models


class StepPackingLabor(models.Model):
    _name = 'step.packing.labor'
    _description = 'Labor / Mano de Obra'
    _order = 'sequence, name'
    _rec_name = 'name'

    name = fields.Char(string='Labor / Mano de Obra', required=True)
    company_id = fields.Many2one('res.company', string='Empresa', default=lambda self: self.env.company)
    sequence = fields.Integer(string='Secuencia', default=10)
    code = fields.Char(string='Código Labor')
    date = fields.Date(string='Fecha')
    is_worker_paid = fields.Boolean(string='Es de Trabajador')
    is_machinery = fields.Boolean(string='Es Maquinaria')
    date_start = fields.Date(string='Fecha Ini Labor')
    date_end = fields.Date(string='Fecha Fin Labor')
    uom_trato_id = fields.Many2one('uom.uom', string='Relación Trato')
    product_tmpl_id = fields.Many2one('product.template', string='Relación Producto')
    activity_id = fields.Many2one('step.packing.activity', string='Actividad')
    is_qa_labor = fields.Boolean(string='¿QA de labor?')
    uom_id = fields.Many2one('uom.uom', string='UdM')
