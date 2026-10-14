# -*- coding: utf-8 -*-
"""Cabecera y flujo comunes de Aserrío y Elaboración.

Flujo (igual que la barra de estado de Studio): Ingresada -> Autorizada ->
Valorizada. Volver a Ingresada desde Valorizada exige el grupo Responsable.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError

PROCESS_STATES = [
    ('draft', 'Ingresada'),
    ('authorized', 'Autorizada'),
    ('valued', 'Valorizada'),
]


class StepSawmillProcessMixin(models.AbstractModel):
    _name = 'step.sawmill.process.mixin'
    _description = 'Cabecera común de procesos de transformación'
    _order = 'date desc, id desc'
    # Código de ir.sequence; lo define cada modelo concreto.
    _sequence_code = None

    name = fields.Char(string='Folio', copy=False, readonly=True, default='Nuevo', tracking=True)
    state = fields.Selection(PROCESS_STATES, string='Estado', default='draft',
                             required=True, copy=False, tracking=True)
    date = fields.Date(string='Fecha', default=fields.Date.context_today, tracking=True)
    user_id = fields.Many2one('res.users', string='Responsable', default=lambda self: self.env.user)
    company_id = fields.Many2one('res.company', string='Empresa', required=True,
                                 default=lambda self: self.env.company)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id')
    production_order_id = fields.Many2one('step.sawmill.production.order', string='Orden de producción')
    work_order_id = fields.Many2one('step.sawmill.work.order', string='Orden de trabajo')
    mrp_production_id = fields.Many2one(
        'mrp.production', string='Orden de fabricación',
        help='Vínculo opcional con la orden de fabricación estándar de Odoo.')
    workcenter_id = fields.Many2one('mrp.workcenter', string='Centro de trabajo')
    process_line_id = fields.Many2one('step.sawmill.process.line', string='Línea / máquina')
    process_type_id = fields.Many2one('step.sawmill.process.type', string='Tipo de proceso')
    shift_id = fields.Many2one('step.sawmill.shift', string='Turno')
    supervisor_id = fields.Many2one('hr.employee', string='Supervisor')
    operator_id = fields.Many2one('hr.employee', string='Operador')
    crew_id = fields.Many2one('step.sawmill.crew', string='Cuadrilla')
    customer_id = fields.Many2one('res.partner', string='Cliente')
    date_start = fields.Datetime(string='Hora inicio')
    date_stop = fields.Datetime(string='Hora término')
    total_hours = fields.Float(string='Total horas', compute='_compute_total_hours',
                               store=True, readonly=False)
    headcount = fields.Integer(string='Dotación total', compute='_compute_headcount',
                               store=True, readonly=False)
    cost_total = fields.Monetary(string='Costo total', compute='_compute_cost_total',
                                 store=True, currency_field='currency_id')
    notes = fields.Html(string='Notas')

    @api.depends('date_start', 'date_stop')
    def _compute_total_hours(self):
        for rec in self:
            if rec.date_start and rec.date_stop and rec.date_stop >= rec.date_start:
                rec.total_hours = (rec.date_stop - rec.date_start).total_seconds() / 3600.0
            else:
                rec.total_hours = rec.total_hours or 0.0

    @api.depends('crew_id', 'crew_id.headcount')
    def _compute_headcount(self):
        for rec in self:
            rec.headcount = rec.crew_id.headcount if rec.crew_id else (rec.headcount or 0)

    @api.depends('cost_ids.cost_total')
    def _compute_cost_total(self):
        for rec in self:
            rec.cost_total = sum(rec.cost_ids.mapped('cost_total'))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if self._sequence_code and (not vals.get('name') or vals.get('name') == 'Nuevo'):
                vals['name'] = self.env['ir.sequence'].next_by_code(self._sequence_code) or 'Nuevo'
        return super().create(vals_list)

    def unlink(self):
        if any(rec.state != 'draft' for rec in self):
            raise UserError(_('Solo se pueden eliminar registros en estado Ingresada.'))
        return super().unlink()

    def action_authorize(self):
        if any(rec.state != 'draft' for rec in self):
            raise UserError(_('Solo se puede autorizar un registro Ingresado.'))
        self.write({'state': 'authorized'})

    def action_value(self):
        if any(rec.state != 'authorized' for rec in self):
            raise UserError(_('Solo se puede valorizar un registro Autorizado.'))
        self.write({'state': 'valued'})

    def action_reset(self):
        if any(rec.state == 'valued' for rec in self) and not self.env.user.has_group(
                'step_sawmill.group_sawmill_manager'):
            raise UserError(_('Solo un Responsable de Aserradero puede reabrir un registro Valorizado.'))
        self.write({'state': 'draft'})
