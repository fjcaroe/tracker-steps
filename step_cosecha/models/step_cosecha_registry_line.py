# © 2025 (Jamie Escalante <jamie.escalante7@gmail.com>)
# -*- coding: utf-8 -*-

import base64
import calendar
from datetime import datetime, date, timedelta
from odoo import api, fields, models, tools, SUPERUSER_ID, _, Command
from odoo.exceptions import UserError, RedirectWarning, ValidationError


class StepCosechaRegistryLine(models.Model):
    _name = 'step.cosecha.registry.line'
    _rec_name = 'employee_id'

    @api.depends('hrs', 'hrs_extra', 'quantity', 'tarifa')
    def _compute_total_hrs(self):
        eta_list = []
        hora_extra = 0
        for move in self:
            if move.tarja_id.state not in ['conta']:
                move.cost_id_domain = self.env['account.analytic.account'].search(
                    [('fundo_id', '=', move.registry_id.fundo_id.id),
                     ('especie_id', '=', move.registry_id.especie_id.id),
                     ('grupo_variedad_id', '=',
                      move.registry_id.grupo_variedad_id.id)]).ids
                if move.registry_id.pricelist_id:
                    for item in move.registry_id.pricelist_id.item_ids:
                        if move.labor_id == item.product_tmpl_id:
                            move.cant_minima = item.min_quantity
                            move.tarifa = item.fixed_price
                            move.uom_id = item.uom_id.id
                move.hrs_total = float(move.hrs) + float(move.hrs_extra)
                if move.tarifa > 0:
                    move.total_trato = float(move.quantity) * float(move.tarifa)
                hoy = date.today()
                ultimo_de_mes = calendar.monthrange(move.date.year, move.date.month)[1]
                dia_semana = str(hoy.weekday())
                hour_count = 0
                for atten in move.contract_id.resource_calendar_id.attendance_ids:
                    if atten.dayofweek == dia_semana and atten.day_period not in ['lunch']:
                        hour_count += atten.hour_to - atten.hour_from
                # horas = move.contract_id.resource_calendar_id.hours_per_day
                horas = (sum(x.hour_to - x.hour_from) for x in move.contract_id.resource_calendar_id.attendance_ids if
                         x.dayofweek == dia_semana and atten.day_period not in ['lunch'])
                # move.sueldo_base = ((float(move.contract_id.sueldo_base) / 30) / 8) * float(move.hrs)
                move.sueldo_base = ((float(move.contract_id.sueldo_base) / int(ultimo_de_mes)) / hour_count) * float(move.hrs)
                if move.hrs_extra > 0:
                    move.valor_hrs_extra = round(0.00777777 * float(move.contract_id.sueldo_base) * float(move.hrs_extra))
                else:
                    move.valor_hrs_extra = 0
                if move.total_trato > 0:
                    move.variable_trato = float(move.total_trato) - float(move.sueldo_base)
                    if move.variable_trato < 0:
                        move.variable_trato = 0
                    if move.registry_id.company_id.sema_corrida_legal:
                        move.sem_corrida = float(move.variable_trato) /  int(move.tarja_id.company_id.sema_corrida) #5
                    else:
                        move.sem_corrida = 0
                    if move.sem_corrida < 0:
                        move.sem_corrida = 0
                move.sab_dom = ((((float(move.contract_id.sueldo_base) / 20) * 2) / 5) / 8) * float(move.hrs)
                if move.registry_id.company_id.gratificacion_legal:
                    move.gratifica = (float(move.sueldo_base) + float(move.valor_hrs_extra) + float(
                        move.variable_trato) + float(move.sem_corrida) + float(move.sab_dom)) *  float(move.registry_id.company_id.gratifica) #0.25
                else:
                    move.gratifica = 0
                move.cost_sueldo = (
                        float(move.sueldo_base) + float(move.valor_hrs_extra) + float(move.variable_trato) + float(
                    move.sem_corrida) + float(move.sab_dom) + float(move.gratifica))
                move.seguro = float(move.cost_sueldo) * move.registry_id.company_id.step_seguro  # 0.07
                move.feriado = float(move.cost_sueldo) * move.registry_id.company_id.step_feriado  # 0.05833
                move.ias = float(move.cost_sueldo) * move.registry_id.company_id.step_ias  # 0.0833
                move.cost_empresa = float(move.cost_sueldo) + float(move.seguro) + float(move.feriado) + float(move.ias)

    employee_id = fields.Many2one('hr.employee', 'Empleado')
    contract_id = fields.Many2one(
        'hr.contract', string='Contrato',
        domain="[('employee_id', '=', employee_id)]", help='Current contract of the employee',
        copy=False)
    registry_id = fields.Many2one(
        comodel_name='step.cosecha.registry',
        string="Cosecha Reference",
        required=True, ondelete='cascade', index=True, copy=False)
    cost_id = fields.Many2one(
        'account.analytic.account', "Centro costos",
    )
    cost_id_domain = fields.Many2many('account.analytic.account', 'registry_cost_rel', 'cost_id',
                                      'registry_id', string='Centro costos', compute='_compute_total_hrs')
    labor_id = fields.Many2one('product.template', 'Labor/Tarea', required=False)
    uom_id = fields.Many2one('uom.uom', 'UdM', required=False)
    quantity = fields.Float(string='Cantidad')
    hrs = fields.Float(string='Hrs. Ord.')
    hrs_extra = fields.Float(string='Hrs. Extra')
    hrs_total = fields.Float(string='Total Hrs.', compute='_compute_total_hrs')
    cant_minima = fields.Float(string='Cant Minima')
    tarifa = fields.Float(string='Tarifa')
    total_trato = fields.Float(string='Total Trato', compute='_compute_total_hrs')
    sueldo_base = fields.Float(string='Sueldo Base')
    valor_hrs_extra = fields.Float(string='Valor Hr Extra', compute='_compute_total_hrs')
    variable_trato = fields.Float(string='Variable trato', compute='_compute_total_hrs')
    sem_corrida = fields.Float(string='Sem Corrida', compute='_compute_total_hrs')
    sab_dom = fields.Float(string='Sab-Dom', compute='_compute_total_hrs')
    gratifica = fields.Float(string='Gratificación', compute='_compute_total_hrs')
    cost_sueldo = fields.Float(string='Costo sueldo', compute='_compute_total_hrs')
    seguro = fields.Float(string='Seguro', compute='_compute_total_hrs')
    feriado = fields.Float(string='Feriado', compute='_compute_total_hrs')
    ias = fields.Float(string='IAS', compute='_compute_total_hrs')
    cost_empresa = fields.Float(string='Costo Empresa', compute='_compute_total_hrs')

    @api.onchange('employee_id', 'hrs', 'hrs_extra')
    def onchange_employee_id(self):
        for record in self:
            if record.employee_id:
                contract_id = self.env['hr.contract'].search(
                    [('employee_id', '=', record.employee_id.id)], limit=1)
                if contract_id:
                    record.contract_id = contract_id.id
                    dia = record.registry_id.date.weekday()
                    if record.hrs > 0:
                        sum_hours = 0
                        sum_hours = sum(
                            (a.hour_to - a.hour_from) for a in contract_id.resource_calendar_id.attendance_ids if
                            a.day_period != 'lunch' and a.dayofweek == str(dia))
                        if record.hrs > sum_hours:
                            raise UserError(
                                _("Las Horas que se ingresaron es mayor a la estipulada para el dia de hoy en los horarios de trabajo del contrato"))
                    if record.hrs_extra > 0:
                        if record.hrs_extra > contract_id.valor_max_extra:
                            raise UserError(
                                _("Las Horas Extras que se ingresaron es mayor a la estipulada en el contrato"))
                else:
                    raise UserError(_("El Empleado %s no posee contrato", record.employee_id.name))

    @api.onchange('hrs')
    def onchange_hrs(self):
        for record in self:
            if record.hrs:
                contract_id = self.env['hr.contract'].search(
                    [('employee_id', '=', record.employee_id.id)], limit=1).id
                if contract_id:
                    record.contract_id = contract_id
                else:
                    raise UserError(_("El Empleado %s no posee contrato", record.employee_id.name))