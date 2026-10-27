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


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    step_work_schedule = fields.Many2one(
        'step.work.schedule', "Horario de Trabajo")
    is_propio =  fields.Boolean('Es Propio')
    is_contratista =  fields.Boolean('Es de Contratista')
    is_super =  fields.Boolean('Supervisor Propio')
    is_super_contratista =  fields.Boolean('Supervisor Propio')
    # super_id = fields.Many2one('hr.employee', string='Supervisor Propio', tracking=True,
    #                              domain="['|', ('company_id', '=', False), ('company_id', 'in', allowed_company_ids)]")
    contratista_id = fields.Many2one('res.partner', string='Nombre Contratista')
    # super_contratista_id = fields.Many2one('hr.employee', string='Supervisor contratista')
    costo_empresa = fields.Monetary('Costo Jornada Empresa', store=True)
    costo_contratista = fields.Monetary('Costo Jornada Contratista', store=True)
    cost_currency_id = fields.Many2one(
        string='Moneda',
        related='company_id.currency_id', readonly=False,
    )