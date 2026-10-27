# © 2025 (Jamie Escalante <jamie.escalante7@gmail.com>)
# -*- coding: utf-8 -*-

import base64
import calendar
from datetime import datetime, date, timedelta
from odoo import api, fields, models, tools, SUPERUSER_ID, _, Command
from odoo.exceptions import UserError, RedirectWarning, ValidationError


class StepTarjaLine(models.Model):
    _name = 'step.tarja.line'
    _rec_name = 'employee_id'

    @api.depends('hrs', 'hrs_extra', 'quantity', 'tarifa')
    def _compute_total_hrs(self):
        eta_list = []
        hora_extra = 0
        for move in self:
            if move.tarja_id.state not in ['conta']:
                # move.cost_id_domain = self.env['account.analytic.account'].search(
                #     [('fundo_id', '=', move.tarja_id.fundo_id.id),
                #      ('especie_id', '=', move.tarja_id.especie_id.id),
                #      ('grupo_variedad_id', 'in',
                #       move.tarja_id.grupo_variedad_id_domain.ids)]).ids
                if move.tarja_id.pricelist_id:
                    if move.tarja_id.pricelist_id.cost_ids:
                        costos = self.env['account.analytic.account'].search(
                            [('id', 'in', move.tarja_id.pricelist_id.cost_ids.ids)])
                        if costos:
                            move.cost_id_domain = costos.ids
                    for item in move.tarja_id.pricelist_id.item_ids:
                        if move.labor_id == item.product_tmpl_id:
                            move.cant_minima = item.min_quantity
                            move.tarifa = item.fixed_price
                            move.uom_id = item.uom_id.id
                move.hrs_total = 0
                move.hrs_total = float(move.hrs) + float(move.hrs_extra)
                if move.tarifa > 0:
                    move.total_trato = float(move.quantity) * float(move.tarifa)
                hoy = date.today()
                ultimo_de_mes = calendar.monthrange(move.tarja_id.date.year, move.tarja_id.date.month)[1]
                dia_semana = str(hoy.weekday())
                hour_count = 0
                horas_sab_dom = []
                for atten in move.contract_id.resource_calendar_id.attendance_ids:
                    if atten.dayofweek not in horas_sab_dom:
                        horas_sab_dom.append(atten.dayofweek)
                    if atten.dayofweek == dia_semana and atten.day_period not in ['lunch']:
                        hour_count += atten.hour_to - atten.hour_from
                #horas = (sum(x.hour_to - x.hour_from) for x in move.contract_id.resource_calendar_id.attendance_ids if x.dayofweek == dia_semana and atten.day_period not in ['lunch'])
                # horas = move.contract_id.resource_calendar_id.hours_per_day
                # mov, compute='_compute_total_hrs'e.sueldo_base = ((float(move.contract_id.sueldo_base)/30)/8) * float(move.hrs)
                if move.hrs > 0 and hour_count > 0:
                    move.sueldo_base = ((float(move.contract_id.sueldo_base)/int(ultimo_de_mes))/hour_count) * float(move.hrs)
                else:
                    move.sueldo_base = 0
                if move.hrs_extra > 0:
                    move.valor_hrs_extra = round(0.00777777 * float(move.contract_id.sueldo_base) * float(move.hrs_extra))
                else:
                    move.valor_hrs_extra = 0
                if move.total_trato > 0:
                    move.variable_trato = float(move.total_trato) - float(move.sueldo_base)
                    if move.variable_trato < 0:
                        move.variable_trato = 0
                    if move.tarja_id.company_id.sema_corrida_legal:
                        move.sem_corrida = float(move.variable_trato) / int(move.tarja_id.company_id.sema_corrida)
                    else:
                        move.sem_corrida = 0
                    if move.sem_corrida < 0:
                        move.sem_corrida = 0
                if '6' in horas_sab_dom:
                    move.sab_dom = (((float(move.contract_id.sueldo_base) /30)*2)/5)
                else:
                    move.sab_dom = (((float(move.contract_id.sueldo_base) /30)*1)/5)
                if move.tarja_id.company_id.gratificacion_legal:
                    move.gratifica = (float(move.sueldo_base)+float(move.valor_hrs_extra)+float(move.variable_trato)+float(move.sem_corrida)+float(move.sab_dom))* float(move.tarja_id.company_id.gratifica) #0.25
                else:
                    move.gratifica = 0
                move.cost_sueldo = (
                            float(move.sueldo_base) + float(move.valor_hrs_extra) + float(move.variable_trato) + float(
                        move.sem_corrida) + float(move.sab_dom) + float(move.gratifica))
                move.seguro = float(move.cost_sueldo)* move.tarja_id.company_id.step_seguro #0.07
                move.feriado = float(move.cost_sueldo)* move.tarja_id.company_id.step_feriado #0.05833
                move.ias = float(move.cost_sueldo)* move.tarja_id.company_id.step_ias #0.0833
                move.cost_empresa = float(move.cost_sueldo)+float(move.seguro)+float(move.feriado)+float(move.ias)
                if not move.cost_id_domain:
                    move.cost_id_domain = []

    employee_id = fields.Many2one('hr.employee', 'Empleado')
    contract_id = fields.Many2one(
        'hr.contract', string='Contrato',
        domain="[('employee_id', '=', employee_id)]", help='Current contract of the employee',
        copy=False)
    tarja_id = fields.Many2one(
        comodel_name='step.tarja',
        string="tarja Reference",
        required=True, ondelete='cascade', index=True, copy=False)
    cost_id = fields.Many2one(
        'account.analytic.account', "Centro costos",
    )
    cost_id_domain = fields.Many2many('account.analytic.account', 'tarja_line_rel', 'cost_id',
                                      'tarja_id', string='Centro costos') #, compute='_compute_total_hrs'
    labor_id = fields.Many2one('product.template', 'Labor/Tarea', required=False)
    uom_id = fields.Many2one('uom.uom', 'UdM', required=False)
    quantity = fields.Float(string='Cantidad')
    hrs = fields.Float(string='Hrs. Ord.')
    hrs_extra = fields.Float(string='Hrs. Extra')
    hrs_total = fields.Float(string='Total Hrs.', compute='_compute_total_hrs', store=True)
    cant_minima = fields.Float(string='Cant Minima')
    tarifa = fields.Float(string='Tarifa')
    total_trato = fields.Float(string='Total Trato', compute='_compute_total_hrs', store=True)
    sueldo_base = fields.Float(string='Sueldo Base')
    valor_hrs_extra = fields.Float(string='Valor Hr Extra', compute='_compute_total_hrs', store=True)
    variable_trato = fields.Float(string='Variable trato', compute='_compute_total_hrs', store=True)
    sem_corrida = fields.Float(string='Sem Corrida', compute='_compute_total_hrs', store=True)
    sab_dom = fields.Float(string='Sab-Dom', compute='_compute_total_hrs', store=True)
    gratifica = fields.Float(string='Gratificación', compute='_compute_total_hrs', store=True)
    cost_sueldo = fields.Float(string='Costo sueldo', compute='_compute_total_hrs', store=True)
    seguro = fields.Float(string='Seguro', compute='_compute_total_hrs', store=True)
    feriado = fields.Float(string='Feriado', compute='_compute_total_hrs', store=True)
    ias = fields.Float(string='IAS', compute='_compute_total_hrs', store=True)
    cost_empresa = fields.Float(string='Costo Empresa', compute='_compute_total_hrs', store=True)
    # informes
    parent_name = fields.Char(related='tarja_id.name', string='Nombre')
    salary_id = fields.Many2one(related='tarja_id.salary_id', string="Cuadrilla")
    salary_id_contrac = fields.Many2one(related='tarja_id.salary_id_contrac', string="Cuadrilla Contratista")
    tarja_type = fields.Selection(related='tarja_id.tarja_type', string='Tipo Tarea')
    partner_id = fields.Many2one(related='tarja_id.partner_id', string='Contratista')
    folio = fields.Char(related='tarja_id.folio', string='Orden de Trabajo')
    date = fields.Date(related='tarja_id.date', string='Fecha')
    user_id = fields.Many2one(related='tarja_id.user_id', string='Usuario')
    fundo_id = fields.Many2one(related='tarja_id.fundo_id', string="Fundo")
    super_id = fields.Many2one(related='tarja_id.super_id', string='Supervisor')
    auto_id = fields.Many2one(related='tarja_id.auto_id', string='Autorizador')
    company_id = fields.Many2one(related='tarja_id.company_id', string='Empresa')
    state = fields.Selection(related='tarja_id.state', string='Estado')
    gratificacion_legal = fields.Boolean(related='tarja_id.gratificacion_legal')
    sema_corrida_legal = fields.Boolean(related='tarja_id.sema_corrida_legal')

    @api.onchange('employee_id', 'hrs', 'hrs_extra')
    def onchange_employee_id(self):
        for record in self:
            if record.employee_id:
                contract_id = self.env['hr.contract'].search(
                [('employee_id', '=', record.employee_id.id)], limit=1)
                if contract_id:
                    record.contract_id = contract_id.id
                    dia = record.tarja_id.date.weekday()
                    if record.hrs > 0:
                        sum_hours = 0
                        sum_hours = sum(
                            (a.hour_to - a.hour_from) for a in contract_id.resource_calendar_id.attendance_ids if
                            a.day_period != 'lunch' and a.dayofweek == str(dia))
                        if record.hrs > sum_hours:
                            raise UserError(_("Las Horas que se ingresaron es mayor a la estipulada para el dia de hoy en los horarios de trabajo del contrato"))
                    if record.hrs_extra > 0:
                        if record.hrs_extra > contract_id.valor_max_extra:
                            raise UserError(_("Las Horas Extras que se ingresaron es mayor a la estipulada en el contrato"))
                else:
                    raise UserError(_("El Empleado %s no posee contrato", record.employee_id.name))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('employee_id'):
                tarja = self.env['step.tarja'].browse(vals['tarja_id'])
                exist = self.env['step.tarja.line'].search(
                [('employee_id', '=', vals['employee_id']), ('date', '=', tarja.date)])
                if exist:
                    employee = self.env['hr.employee'].browse(vals['employee_id'])
                    raise UserError(_("El Empleado %s ya posee un Registro para la fecha %s", employee.name, tarja.date))
        return super(StepTarjaLine, self).create(vals_list)
