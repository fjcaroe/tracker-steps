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


class ResPartner(models.Model):
    _inherit = 'res.partner'

    step_export =  fields.Boolean('Exportación?')
    is_productor =  fields.Boolean('Es Productor?')
    step_contra =  fields.Boolean('Proveedor Contratista')
    step_carga =  fields.Boolean('Transporte de carga?')
    productor_name = fields.Char(string='Nombre productor')
    cod_fundo = fields.Char(string='Código fundo', index=True)
    cod_csg = fields.Char(string='Código CSG', index=True)
    cod_ggn = fields.Char(string='Código GGN', index=True)
    duplicate_bank_partner_ids = fields.Boolean() # bug