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


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    is_fruta =  fields.Boolean('Es Fruta?')
    cosecha =  fields.Boolean('Es Cosecha?')
    is_labor =  fields.Boolean('Es Labor, Tarea?')
    is_flete =  fields.Boolean('Es flete?')
    is_bpa =  fields.Boolean('Es BPA?')
    dia_carencia = fields.Integer(string='Días de carencia')
    hrs_reingreso = fields.Float(string='Horas de reingreso')
    step_ingrediente = fields.Char(string='Ingrediente activo')
    step_toxi = fields.Char(string='Toxicidad')
    step_class = fields.Char(string='Clasificación')
    step_objetivo = fields.Char(string='Objetivo/plaga a combatir')
    step_equi = fields.Char(string='Equipamiento de uso')
    step_epp = fields.Boolean(string='EPP')
    step_proteje = fields.Char(string='Que proteje')
    actividad_id = fields.Many2one(
        'account.analytic.account', "Actividad",
    )
    #page actividades
    cod_labor = fields.Char(string='Código Labor')
    # uom_id = fields.Many2one('uom.uom', 'UdM', required=True)
    uom_trato = fields.Many2one('uom.uom', 'Relación Trato', required=False)
    # actividad_id = fields.Many2one('step.actividad', required=True)
    grupo_labor = fields.Selection(
        selection=[
            ('manten', 'Mantencion'),
            ('cosecha', 'Cosecha'),
            ('inver', 'Invercion'),
            ('pack', 'Packing'),
        ],
        string='Grupo Labor',
        required=True,
        readonly=False,
        copy=False,
    )
    met_costeo = fields.Selection(
        selection=[
            ('kilo', 'Por Kilo'),
            ('udm', 'Por Udm'),
            ('driver', 'Driver'),
            ('numeral', 'Numeral'),
        ],
        string='Método Costeo',
        required=False,
        readonly=False,
        copy=False,
    )
    es_trabajador = fields.Boolean(string='Es de Trabajador')
    es_maquina = fields.Boolean(string='Es Maquinaria')
    qa = fields.Boolean(string='QA de labor?')
    # product_id = fields.Many2one('product.template', 'Relación Producto', required=False)
    partner_id = fields.Many2one('res.partner', 'Responsable')
    date = fields.Date(string='Fecha')
    # company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    date_init = fields.Date(string='Fecha Inicio Labor')
    date_end = fields.Date(string='Fecha Fin Labor ')
    # actividad_id = fields.Many2one('step.actividad',
    #                                string="Actividad",
    #                                required=True, ondelete='cascade')