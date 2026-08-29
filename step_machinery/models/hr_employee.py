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

    is_tractorista =  fields.Boolean('Tractorista')
    is_aplicador =  fields.Boolean('Aplicador')
    is_res_registro =  fields.Boolean('Responsable Registro')
    is_admin =  fields.Boolean('Administrador')
    is_dosifi =  fields.Boolean('Dosificador')