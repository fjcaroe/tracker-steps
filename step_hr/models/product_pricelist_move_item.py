# © 2025 (Jamie Escalante <jamie.escalante7@gmail.com>)
# -*- coding: utf-8 -*-

import logging
import random
import math
import pytz

from collections import defaultdict, Counter
from datetime import date, datetime, time
from dateutil.relativedelta import relativedelta
from functools import reduce

from odoo import api, Command, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_round, date_utils, convert_file, format_amount
from odoo.tools.float_utils import float_compare
from odoo.tools.misc import format_date
from odoo.tools.safe_eval import safe_eval, datetime as safe_eval_datetime, dateutil as safe_eval_dateutil


class ProductPricelistMoveLine(models.Model):
    _name = 'product.pricelist.move.line'
    _rec_name = 'product_id'


    recorrido_id = fields.Many2one('hr.route', 'Tipo Recorrido', required=False)
    product_id = fields.Many2one(related='recorrido_id.product_id', string='Tramo Servicio', required=True)
    desde = fields.Char(related='recorrido_id.desde', string='Lugar Desde')
    hasta = fields.Char(related='recorrido_id.hasta', string='Lugar Hasta')
    t_viaje = fields.Float(related='recorrido_id.time_recorrido', string='Tiempo de Viaje')
    cobro_type = fields.Selection(related='recorrido_id.travel_type', string='Tipo Cobro')
    min_quantity = fields.Integer(string='Minimo Pasajeros')
    tarifa = fields.Float(string='Tarifa')
    pricelist_id = fields.Many2one(
        comodel_name='product.pricelist',
        string="Tarifa Reference",
        required=True, ondelete='cascade', index=True, copy=False)

    # @api.onchange('recorrido_id')
    # def onchange_recorrido_id(self):
    #     if self.recorrido_id:
    #         self.product_id = self.recorrido_id.product_id
