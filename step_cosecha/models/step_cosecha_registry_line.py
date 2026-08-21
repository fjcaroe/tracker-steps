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

    @api.depends(
        'hrs', 'hrs_extra', 'quantity', 'tarifa', 'labor_id', 'contract_id',
        'registry_id.date', 'registry_id.fundo_id', 'registry_id.especie_id',
        'registry_id.grupo_variedad_id', 'registry_id.pricelist_id',
    )
    def _compute_total_hrs(self):
        for move in self:
            registry = move.registry_id
            company = registry.company_id

            # Every computed field must receive a value, even on old or partially
            # imported records.  The former implementation was copied from the
            # Tarjas model and referenced ``tarja_id`` and ``move.date``, neither
            # of which exists on a harvest registry line.
            move.cost_id_domain = self.env['account.analytic.account']
            move.hrs_total = float(move.hrs or 0.0) + float(move.hrs_extra or 0.0)
            move.total_trato = 0.0
            move.valor_hrs_extra = 0.0
            move.variable_trato = 0.0
            move.sem_corrida = 0.0
            move.sab_dom = 0.0
            move.gratifica = 0.0
            move.cost_sueldo = 0.0
            move.seguro = 0.0
            move.feriado = 0.0
            move.ias = 0.0
            move.cost_empresa = 0.0

            if not registry:
                continue

            move.cost_id_domain = self.env['account.analytic.account'].search([
                ('fundo_id', '=', registry.fundo_id.id),
                ('especie_id', '=', registry.especie_id.id),
                ('grupo_variedad_id', '=', registry.grupo_variedad_id.id),
            ])

            if registry.pricelist_id and move.labor_id:
                item, unit_price = registry._get_cosecha_unit_price(
                    move.labor_id, move.quantity, move.uom_id
                )
                if item:
                    move.cant_minima = item.min_quantity
                    move.tarifa = unit_price
                    if item.uom_id:
                        move.uom_id = item.uom_id

            move.total_trato = float(move.quantity or 0.0) * float(move.tarifa or 0.0)

            contract = move.contract_id
            calendar_id = contract.resource_calendar_id if contract else False
            registry_date = fields.Datetime.to_datetime(registry.date) if registry.date else False
            base_salary = float(contract.sueldo_base or 0.0) if contract else 0.0
            salary_cost = float(move.sueldo_base or 0.0)

            if registry_date and calendar_id and base_salary:
                day_of_week = str(registry_date.weekday())
                scheduled_hours = sum(
                    attendance.hour_to - attendance.hour_from
                    for attendance in calendar_id.attendance_ids
                    if attendance.dayofweek == day_of_week
                    and attendance.day_period != 'lunch'
                )
                if scheduled_hours > 0:
                    month_days = calendar.monthrange(
                        registry_date.year, registry_date.month
                    )[1]
                    salary_cost = (
                        (base_salary / month_days) / scheduled_hours
                    ) * float(move.hrs or 0.0)
                    move.sueldo_base = salary_cost

            if base_salary and move.hrs_extra:
                move.valor_hrs_extra = round(
                    0.00777777 * base_salary * float(move.hrs_extra)
                )

            move.variable_trato = max(move.total_trato - salary_cost, 0.0)
            sema_corrida = float(company.sema_corrida or 0.0)
            if company.sema_corrida_legal and sema_corrida > 0:
                move.sem_corrida = move.variable_trato / sema_corrida

            if base_salary:
                move.sab_dom = (
                    (((base_salary / 20) * 2) / 5) / 8
                ) * float(move.hrs or 0.0)

            subtotal = (
                salary_cost + move.valor_hrs_extra + move.variable_trato
                + move.sem_corrida + move.sab_dom
            )
            if company.gratificacion_legal:
                move.gratifica = subtotal * float(company.gratifica or 0.0)

            move.cost_sueldo = subtotal + move.gratifica
            move.seguro = move.cost_sueldo * float(company.step_seguro or 0.0)
            move.feriado = move.cost_sueldo * float(company.step_feriado or 0.0)
            move.ias = move.cost_sueldo * float(company.step_ias or 0.0)
            move.cost_empresa = (
                move.cost_sueldo + move.seguro + move.feriado + move.ias
            )

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
