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

    @api.depends(
        'consumption_line.concept_amount', 'consumption_line.cost_hr_amount',
        'radio_line.concept_amount', 'radio_line.cost_hr_amount',
        'step_total_hrs_mes', 'step_cost_hrs',
    )
    def _compute_costo(self):
        for vehicle in self:
            def hourly(lines):
                explicit = sum(lines.mapped('cost_hr_amount'))
                if explicit:
                    return explicit
                return (sum(lines.mapped('concept_amount')) / vehicle.step_total_hrs_mes
                        if vehicle.step_total_hrs_mes else 0.0)

            vehicle.step_man_hrs = hourly(vehicle.consumption_line)
            vehicle.step_propo_hrmq = hourly(vehicle.radio_line)
            vehicle.step_cost_hrmq_standar = (
                vehicle.step_cost_hrs + vehicle.step_man_hrs + vehicle.step_propo_hrmq
            )

    consumption_line = fields.One2many(
        comodel_name='monthly.consumption.line',
        inverse_name='vehicle_id',
        string="Monthly Consumption Lines",
        copy=True, auto_join=True)
    radio_line = fields.One2many(
        comodel_name='monthly.radio.line',
        inverse_name='vehicle_id',
        string="Monthly Radio Lines",
        copy=True, auto_join=True)
    es_maquina = fields.Boolean(string='Es Maquinaria')
    step_propo_hrmq = fields.Float(compute='_compute_costo', store=True)
    step_man_hrs = fields.Float(compute='_compute_costo', store=True)
    step_cost_hrmq_standar = fields.Float(
        string='Costo Hr/Mq estándar', compute='_compute_costo', store=True,
    )
