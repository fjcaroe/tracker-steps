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


class HrSalaryCustomLine(models.Model):
    _name = 'hr.salary.custom.line'
    _rec_name = 'employee_id'

    # name = fields.Char(string='Descripción', index=True)
    cod_nip = fields.Char(related='employee_id.pin', string='Código NIP', index=True)
    employee_id = fields.Many2one('hr.employee', 'Trabajador')
    contract_id = fields.Many2one(
        'hr.contract', string='Contrato',
        domain="[('employee_id', '=', employee_id)]", help='Current contract of the employee',
        copy=False)
    hours = fields.Float('Horas Diarias')
    salary_id = fields.Many2one(
        comodel_name='hr.salary.custom',
        string="Salary Reference",
        required=True, ondelete='cascade', index=True, copy=False)
    #Informes line
    parent_name = fields.Char(related='salary_id.name', string='Nombre')
    folio = fields.Char(related='salary_id.folio', string='Folio')
    group_type = fields.Selection(related='salary_id.group_type', string='Tipo Cuadrilla')
    date = fields.Date(related='salary_id.date', string='Fecha')
    partner_id = fields.Many2one(related='salary_id.partner_id', comodel_name='res.partner', string='Contratista')
    employee_supervisor_id = fields.Many2one(related='salary_id.employee_id', comodel_name='hr.employee', string='Supervisor')
    date_init = fields.Datetime(related='salary_id.date_init', string="Hora entrada")
    date_to = fields.Datetime(related='salary_id.date_to', string="hora salida")
    responsable_id = fields.Many2one(related='salary_id.responsable_id', comodel_name="hr.employee", string="Responsable")
    company_id = fields.Many2one(related='salary_id.company_id', comodel_name='res.company', string='Compañía')
    fundo_id = fields.Many2one(related='salary_id.fundo_id', comodel_name='step.fundo', string="Fundo")
    state = fields.Selection(related='salary_id.state', string="Estado")
