# -*- coding: utf-8 -*-
# Puerto desde Studio (steps_qa, x_stock_picking_line_547ac) - ticket 34.
from odoo import fields, models


class StepPackingPickingTagLine(models.Model):
    _name = 'step.packing.picking.tag.line'
    _description = 'Detalle de tarja en recepción de fruta'
    _order = 'picking_id, sequence, id'

    picking_id = fields.Many2one('stock.picking', string='Traslado', required=True, ondelete='cascade', index=True)
    company_id = fields.Many2one(related='picking_id.company_id', store=True)
    sequence = fields.Integer(string='Secuencia', default=10)
    tag_number = fields.Char(string='Número de tarja')
    packaging_id = fields.Many2one('product.packaging', string='Embalaje')
    caliber_id = fields.Many2one('step.packing.fruit.caliber', string='Calibre')
    category_id = fields.Many2one('step.packing.fruit.category', string='Categoría de fruta')
    brand = fields.Char(string='Marca / etiqueta')
    quantity = fields.Float(string='Cantidad de embalajes', digits='Product Unit of Measure')
    kilos = fields.Float(string='Kilos', digits='Stock Weight')
    uom_id = fields.Many2one('uom.uom', string='Unidad de medida')
