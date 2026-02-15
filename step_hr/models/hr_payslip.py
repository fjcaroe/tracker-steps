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


class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    @api.depends('line_ids.total')
    def _compute_net_liquido(self):
        line_values = (self._origin)._get_line_values(['LIQ'])
        for payslip in self:
            payslip.net_liquido = line_values['LIQ'][payslip._origin.id]['total']

    net_liquido = fields.Monetary(string='Alcance Liquido', compute='_compute_net_liquido', store=True)

    # def action_refresh_from_work_entries(self):
    #     res = super(HrPayslip, self).action_refresh_from_work_entries()
    #     # Refresh the whole payslip in case the HR has modified some work entries
    #     # after the payslip generation
    #     res.mapped('input_line_ids').unlink()
    #     res._compute_worked_days_line_ids()
