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


class HrContract(models.Model):
    _inherit = 'hr.contract'

    @api.depends('wage', 'valor_extra', 'otro_impo', 'step_ias_factor', 'fer_propor_factor', 'aport_patronal_factor', 'step_seguro_factor', 'step_sis_factor')
    def _compute_total(self):
        eta_list = []
        hora_extra = 0
        for move in self:
            move.sueldo_base = move.wage
            move.grati = (float(move.sueldo_base) + float(
                move.otro_impo)) * 0.25
            move.total_impo = (float(move.sueldo_base)  + float(
                move.grati) + float(move.otro_impo))
            move.step_sis = (float(move.total_impo) * float(move.step_sis_factor))/100
            move.step_ias = (float(move.total_impo) * float(move.step_ias_factor))/100
            move.step_seguro = (float(move.total_impo) * float(move.step_seguro_factor))/100
            move.aport_patronal = (float(move.total_impo) * float(move.aport_patronal_factor))/100
            move.fer_propor = (float(move.total_impo) * float(move.fer_propor_factor))/100
            move.total_cost = (float(move.total_impo) + float(move.otro_no_imp) + float(
                move.step_sis) + float(move.step_seguro) + float(
                move.aport_patronal) + float(move.fer_propor) + float(
                move.step_ias))
            move.cost_dia = move.total_cost / 22
            move.cost_hora = move.total_cost / (int(move.resource_calendar_id.hours_per_week)*4) or 0

    sueldo_base =  fields.Float('Sueldo base', compute='_compute_total', store=True)
    valor_extra =  fields.Float('Valor Hora Extra')
    valor_max_extra =  fields.Integer('Horas extras máximas por día', default=2)
    grati =  fields.Float('Gratificación', compute='_compute_total', store=True)
    otro_impo =  fields.Float('Otro Imponible')
    total_impo =  fields.Float('Total Imponible', compute='_compute_total', store=True)
    otro_no_imp =  fields.Float('Otros No Imponibles')
    total_cost =  fields.Float('Total Costo Mes', compute='_compute_total', store=True)
    cost_dia =  fields.Float('Costo diario', compute='_compute_total', store=True)
    cost_hora =  fields.Float('Costo Hora', compute='_compute_total', store=True)
    step_sis =  fields.Float('SIS', compute='_compute_total', store=True)
    step_sis_factor =  fields.Float('SIS Factor', digits=(16, 5), default=1.78)
    step_seguro =  fields.Float('Seguro', compute='_compute_total', store=True)
    step_seguro_factor =  fields.Float('Seguro factor', digits=(16, 5), default=3.0)
    aport_patronal =  fields.Float('Aporte patronal', compute='_compute_total', store=True)
    aport_patronal_factor =  fields.Float('Aporte patronal factor', digits=(16, 5), default=1.0)
    fer_propor =  fields.Float('Feriado Proporcional', compute='_compute_total', store=True)
    fer_propor_factor =  fields.Float('Feriado Proporcional factor', digits=(16, 5), default=5.83000)
    step_ias =  fields.Float('IAS', compute='_compute_total', store=True)
    step_ias_factor =  fields.Float('IAS factor', digits=(16, 5), default=8.33)