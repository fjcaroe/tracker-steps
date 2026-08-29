# -*- coding: utf-8 -*-

from odoo import fields, models


class ProductPricelistMoveLine(models.Model):
    _name = 'product.pricelist.move.line'
    _description = 'Tarifa de movilización por recorrido'
    _rec_name = 'recorrido_id'

    recorrido_id = fields.Many2one('hr.route', 'Recorrido', required=True)
    product_id = fields.Many2one(related='recorrido_id.product_id', string='Servicio', required=True)
    desde = fields.Char(related='recorrido_id.desde', string='Lugar desde')
    hasta = fields.Char(related='recorrido_id.hasta', string='Lugar hasta')
    t_viaje = fields.Float(related='recorrido_id.time_recorrido', string='Tiempo de viaje')
    cobro_type = fields.Selection(related='recorrido_id.travel_type', string='Sentido')
    charge_type = fields.Selection(
        selection=[
            ('fixed', 'Fija'),
            ('per_passenger', 'Por pasajero'),
            ('minimum', 'Mínima'),
            ('proportional', 'Proporcional'),
        ],
        string='Tipo de tarifa', required=True, default='fixed',
        help='Define explícitamente cómo se calcula el cobro; el costeo no debe inferirlo.')
    min_quantity = fields.Integer(string='Mínimo de pasajeros')
    tarifa = fields.Float(string='Tarifa', required=True)
    currency_id = fields.Many2one('res.currency', string='Moneda',
                                   default=lambda self: self.env.company.currency_id)
    date_start = fields.Date(string='Vigente desde')
    date_end = fields.Date(string='Vigente hasta')
    pricelist_id = fields.Many2one('product.pricelist', string="Lista de tarifa",
                                    required=True, ondelete='cascade', index=True, copy=False)
