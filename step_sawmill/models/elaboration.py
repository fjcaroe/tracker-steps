# -*- coding: utf-8 -*-
from odoo import fields, models


class StepSawmillElaboration(models.Model):
    _name = 'step.sawmill.elaboration'
    _description = 'Elaboración'
    _inherit = ['step.sawmill.process.mixin', 'mail.thread', 'mail.activity.mixin']
    _sequence_code = 'step.sawmill.elaboration'

    # En Studio la Elaboración solo tenía cabecera; el detalle (productos,
    # consumos y valorización) reutiliza las mismas líneas de Aserrío.
    output_ids = fields.One2many('step.sawmill.output.line', 'elaboration_id', string='Productos obtenidos')
    input_ids = fields.One2many('step.sawmill.input.line', 'elaboration_id', string='Materia prima consumida')
    cost_ids = fields.One2many('step.sawmill.cost.line', 'elaboration_id', string='Valorización')
