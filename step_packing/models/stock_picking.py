# -*- coding: utf-8 -*-
# Puerto desde Studio (steps_qa, app Packing Fruta) a codigo real - ticket 34.
# En Studio la "Recepcion fruta" y el "Despacho" eran traslados estandar
# (stock.picking) con campos x_studio_* agregados; aqui son campos propios.
from odoo import fields, models


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    # Origen de la fruta (x_studio_fundo, x_studio_especie, ...).
    fruit_fundo_id = fields.Many2one('step.fundo', string='Productor - Fundo', index=True)
    fruit_species_id = fields.Many2one('step.especie', string='Especie', index=True)
    fruit_variety_id = fields.Many2one(
        'step.variedad', string='Variedad',
        domain="[('especie_id', '=?', fruit_species_id)]")
    fruit_category_id = fields.Many2one('step.packing.fruit.category', string='Categoría de fruta')
    fruit_class_id = fields.Many2one('step.packing.fruit.class', string='Clase de origen')
    fruit_type = fields.Char(string='Tipo de fruta')
    fruit_season_id = fields.Many2one('step.temporada', string='Temporada')
    fruit_lot = fields.Char(string='Lote')
    fruit_harvest_date = fields.Date(string='Fecha de cosecha')
    fruit_guide_number = fields.Char(string='Número de guía')
    fruit_weighing_type = fields.Char(string='Tipo de pesaje')
    fruit_grower_contract = fields.Char(string='Contrato productor')

    # Flete (x_studio_paga_flete, x_studio_patente_camin, ...).
    fruit_freight_paid = fields.Boolean(string='Paga flete')
    fruit_carrier_id = fields.Many2one('res.partner', string='Transportista')
    fruit_truck_plate = fields.Char(string='Patente camión')
    fruit_freight_route = fields.Char(string='Tramo')
    fruit_freight_rate = fields.Float(string='Tarifa flete', digits='Product Price')

    # Detalle de tarjas recibidas (x_stock_picking_line_547ac en Studio).
    fruit_tag_line_ids = fields.One2many(
        'step.packing.picking.tag.line', 'picking_id', string='Detalle de tarjas', copy=True)
