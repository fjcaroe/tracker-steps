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


class FleetVehicle(models.Model):
    _inherit = 'fleet.vehicle'

    @api.depends('step_litros_hrmq', 'step_cost_unid')
    def _compute_costo_hrmq(self):
        for prod in self:
            try:
                if int(prod.step_litros_hrmq) > 0 and int(prod.step_cost_unid) > 0:
                    prod.step_cost_hrs = float(prod.step_litros_hrmq) * float(prod.step_cost_unid)
                else:
                    prod.step_cost_hrs = 0
            except ZeroDivisionError:
                prod.step_cost_hrs = 0



    cost_id = fields.Many2one(
        'account.analytic.account', "Centro costos",
    )
    analytic_id = fields.Many2one(
        'account.analytic.account', "Cuenta analítica",
    )
    # transmision = fields.Selection(string='Transmisión',
    #                                selection=[('auto', 'Automático'),
    #                                           ('manual', 'Manual')],
    #                                )
    # step_asiento =  fields.Integer('Número de asientos')
    # step_puerta =  fields.Integer('Número de puertas')
    # step_enganche =  fields.Boolean('Enganche de remolque')
    mod_carga = fields.Selection(string='Modalidad de carga',
                                   selection=[('ram', 'Rampa Plana'),
                                              ('cerrado', 'Cerrado sin frio'),
                                              ('frigo', 'Frigorífico')],
                                   )
    step_tonelada = fields.Integer('Toneladas')
    step_mtrs_cub = fields.Integer('Metros cúbicos')
    step_litros = fields.Integer('Litros')
    step_cant_pallet = fields.Integer('Cantidad Pallet')
    step_cant_bins = fields.Integer('Cantidad Bins')
    step_product_id = fields.Many2one('product.template', 'Producto', required=False)
    step_litros_hrmq = fields.Float('Litros por HrMq')
    step_cost_unid = fields.Float('Costo por Unidad')
    step_cost_hrs = fields.Float('Costo por hora', compute='_compute_costo_hrmq', store=True)
    step_propo_hrmq = fields.Float('Costo Proporción HrMq')
    step_man_hrs = fields.Float('Costo mantención hora')
    step_total_hrs_mes = fields.Float('Total hora estándar mes')
    step_cost_hrmq_standar = fields.Float('Costo Hr/Mq estándar')