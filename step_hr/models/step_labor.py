# © 2025 (Jamie Escalante <jamie.escalante7@gmail.com>)
# -*- coding: utf-8 -*-

import base64
from odoo import api, fields, models, tools, SUPERUSER_ID, _, Command


class StepLabor(models.Model):
    _name = 'step.labor'

    name = fields.Char(string='Nombre', index=True, required=True)
    cod_labor = fields.Char(string='Código Labor')
    uom_id = fields.Many2one('uom.uom', 'UdM', required=True)
    uom_trato = fields.Many2one('uom.uom', 'Relación Trato', required=True)
    actividad_id = fields.Many2one('step.actividad', required=True)
    grupo_labor = fields.Selection(
        selection=[
            ('manten', 'Mantencion'),
            ('cosecha', 'Cosecha'),
            ('inver', 'Invercion'),
            ('pack', 'Packing'),
        ],
        string='Grupo Labor',
        required=True,
        readonly=False,
        copy=False,
    )
    met_costeo = fields.Selection(
        selection=[
            ('kilo', 'Por Kilo'),
            ('udm', 'Por Udm'),
            ('driver', 'Driver'),
            ('numeral', 'Numeral'),
        ],
        string='Método Costeo',
        required=True,
        readonly=False,
        copy=False,
    )
    es_trabajador = fields.Boolean(string='Es de Trabajador')
    es_maquina = fields.Boolean(string='Es Maquinaria')
    qa = fields.Boolean(string='QA de labor?')
    product_id = fields.Many2one('product.template', 'Relación Producto', required=False)
    partner_id = fields.Many2one('res.partner', 'Responsable')
    date = fields.Date(string='Fecha')
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    date_init = fields.Date(string='Fecha Ini Labor')
    date_end = fields.Date(string='Fecha Fin Labor ')
    actividad_id = fields.Many2one('step.actividad',
        string="Actividad",
        required=True, ondelete='cascade')
    labor_line = fields.One2many(
        comodel_name='step.labor.line',
        inverse_name='labor_id',
        string="Labor Lines",
        copy=True, auto_join=True)