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


class HrSalaryCustom(models.Model):
    _name = 'hr.salary.custom'
    _inherit = ['mail.thread']

    @api.model
    def default_get(self, fields):
        res = super(HrSalaryCustom, self).default_get(fields)
        if self.env.context.get('step_default_contratista'):
            res.update({
                'group_type': 'contratista'
            })
        if self.env.context.get('step_default_propio'):
            res.update({
                'group_type': 'propio'
            })
        return res

    name = fields.Char(string='Nombre', index=True)
    folio = fields.Char(string='Folio', index=True)
    group_type = fields.Selection(string='Tipo Cuadrilla',
                                     selection=[('propio', 'Propio'),
                                                ('contratista', 'Contratista')])
    date = fields.Date(string='Fecha', default=fields.Date.context_today, tracking=True)
    partner_id = fields.Many2one('res.partner', 'Contratista')
    employee_id = fields.Many2one('hr.employee', 'Supervisor')
    date_init = fields.Datetime(string="Hora entrada")
    fundo_id = fields.Many2one('step.fundo',
                               string="Fundo",
                               required=False, ondelete='cascade', copy=False)
    date_to = fields.Datetime(string="hora salida")
    responsable_id = fields.Many2one("hr.employee", string="Responsable")
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    work_entry_type_id = fields.Many2one(
        'hr.work.entry.type', 'Concepto Sueldo')
    salary_line = fields.One2many(
        comodel_name='hr.salary.custom.line',
        inverse_name='salary_id',
        string="Salary Custom Lines",
        copy=True, auto_join=True)
    contract_line = fields.One2many(
        comodel_name='hr.salary.contract.line',
        inverse_name='salary_id',
        string="Salary Custom Lines",
        copy=True, auto_join=True)
    state = fields.Selection(
        selection=[
            ('draft', 'Nuevo'),
            ('progress', 'En progreso'),
            ('done', 'Listo'),
        ],
        string='Estado',
        required=True,
        readonly=False,
        copy=False,
        default='draft',
    )
    payslip_run_id = fields.Many2one('hr.payslip.run', string="Lote", required=False)
    struct_id = fields.Many2one('hr.payroll.structure', string="Estructura Salarial", required=False)
    # contract_id = fields.Many2one(
    #     'hr.contract', string='Contrato',
    #     domain="[('company_id', '=', company_id), ('employee_id', '=', employee_id)]", help='Current contract of the employee',
    #     copy=False)

    def action_draft(self):
        for salary in self:
            salary.write({'state': 'draft'})

    def action_progress(self):
        for salary in self:
            salary.write({'state': 'progress'})

    @api.model
    def create(self, vals):
        if vals.get("group_type") == 'propio':
            seq = str(self.env['ir.sequence'].next_by_code('cuadrilla_propia_seq'))
            vals["name"] = seq + '-' + str(vals["name"])
        if vals.get("group_type") == 'contratista':
            seq = str(self.env['ir.sequence'].next_by_code('cuadrilla_contratista_seq'))
            vals["name"] = seq + '-' + str(vals["name"])
        return super(HrSalaryCustom, self).create(vals)