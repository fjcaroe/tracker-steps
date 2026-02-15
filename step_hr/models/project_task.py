# © 2025 (Jamie Escalante <jamie.escalante7@gmail.com>)
# -*- coding: utf-8 -*-

from ast import literal_eval
from typing import Dict, List
import pytz

from odoo import Command, fields, models, api, _
from odoo.osv import expression
from odoo.tools import get_lang
from odoo.addons.resource.models.utils import Intervals, sum_intervals

class Task(models.Model):
    _inherit = "project.task"

    num_op = fields.Char(string='Número OP', readonly=False)
    grupo_variedad_id = fields.Many2one('step.grupo.variedad',
                                        string="Grupo Variedad",
                                        required=True, ondelete='cascade', copy=False)
    variedad_id = fields.Many2one('step.variedad',
                                  string="Variedad",
                                  required=True, ondelete='cascade', copy=False)
    step_note = fields.Html(string="Notas")
    cost_id = fields.Many2one(
        'account.analytic.account', "Centro de Costo",
        check_company=True)