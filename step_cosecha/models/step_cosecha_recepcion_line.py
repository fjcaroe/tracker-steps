# © 2025 (Jamie Escalante <jamie.escalante7@gmail.com>)
# -*- coding: utf-8 -*-

import base64
from odoo import api, fields, models, tools, SUPERUSER_ID, _, Command


class StepCosechaRecepcionLine(models.Model):
    _name = 'step.cosecha.recepcion.line'
    _description = 'Detalle de Recepción de Cosecha'
    _rec_name = 'product_id'
    _order = 'id'
    _sql_constraints = [
        ('step_reception_quantity_nonnegative', 'CHECK(quantity >= 0)', 'Los kilos no pueden ser negativos.'),
        ('step_reception_boxes_nonnegative', 'CHECK(boxes >= 0)', 'Las cajas no pueden ser negativas.'),
    ]

    employee_id = fields.Many2one('hr.employee', 'Empleado')
    # employee_id_domain = fields.Many2many('hr.employee', 'tarja_employee_rel', 'employee_id',
    #                                       'tarja_id', string='Empleados', compute='compute_total_trato')
    recep_id = fields.Many2one(
        comodel_name='step.cosecha.recepcion',
        string="Cosecha",
        required=True, ondelete='cascade', index=True, copy=False)
    product_id = fields.Many2one(
        'product.template', string='Producto', domain="[('is_fruta', '=', True)]"
    )
    packaging_id = fields.Many2one('product.packaging', string='Tipo de envase')
    uom_id = fields.Many2one('uom.uom', string='Unidad de medida')
    quantity = fields.Float(string='Kilos recibidos', digits='Product Unit of Measure')
    boxes = fields.Float(string='Cajas / envases')
    tarja = fields.Char(string='Tarja / lote')
    temperature = fields.Float(string='Temperatura °C', digits=(12, 2))
    quality = fields.Selection(
        selection=[
            ('approved', 'Aprobada'),
            ('observed', 'Observada'),
            ('rejected', 'Rechazada'),
        ],
        string='Calidad',
        default='approved',
        required=True,
    )
    note = fields.Char(string='Observación')
