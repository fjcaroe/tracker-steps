# © 2025 (Jamie Escalante <jamie.escalante7@gmail.com>)
# -*- coding: utf-8 -*-

import base64
import calendar
from odoo import api, fields, models, tools, SUPERUSER_ID, _, Command
from datetime import datetime, date, timedelta


class RealCostMachinery(models.Model):
    _name = 'real.cost.machinery'
    _inherit = ['mail.thread']

    @api.depends('date')
    def compute_temporada(self):
        for move in self:
            move.temp_id = self.env['step.temporada'].search(
                [('start_date', '<=', move.date),
                 ('end_date', '>=', move.date)], limit=1).id

    @api.depends('real_cost_machinery_line', 'regist_cost_machinery_line')
    def compute_cost_total(self):
        for move in self:
            move.cost_amount = sum(x.monto for x in move.real_cost_machinery_line)
            move.total_hrs = sum(x.hrs_maquina for x in move.regist_cost_machinery_line)
            try:
                move.total_cost = move.cost_amount / move.total_hrs
            except ZeroDivisionError:
                move.total_cost = 0


    name = fields.Char(string='Nombre', index=True, required=True)
    date = fields.Date(string='Fecha')
    date_init = fields.Date(string='Periodo Inicio')
    date_to = fields.Date(string='Periodo Fin')
    fundo_id = fields.Many2one('step.fundo',
                               string="Fundo",
                               required=False, ondelete='cascade', copy=False)
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    temp_id = fields.Many2one("step.temporada", string="Temporada", compute='compute_temporada', store=True)
    responsable_id = fields.Many2one("hr.employee", string="Responsable")
    state = fields.Selection(
        selection=[
            ('draft', 'Nuevo'),
            ('costo', 'Costeo'),
            ('conta', 'Contabilizado'),
        ],
        string='Estado',
        required=True,
        readonly=False,
        copy=False,
        default='draft',
    )
    machinery_ids = fields.Many2one(
        comodel_name='fleet.vehicle',
        string="Maquinaria",
        required=True, ondelete='cascade', index=True, copy=False)
    cost_id = fields.Many2one(
        'account.analytic.account', "Centro costos",
    )
    real_cost_machinery_line = fields.One2many(
        comodel_name='real.cost.machinery.line',
        inverse_name='real_cost_id',
        string="Machinery Lines",
        copy=True, auto_join=True)
    regist_cost_machinery_line = fields.One2many(
        comodel_name='regist.cost.machinery.line',
        inverse_name='regist_cost_id',
        string="Machinery Lines",
        copy=True, auto_join=True)
    total_hrs = fields.Float(string='Total de Horas', compute='compute_cost_total', store=True)
    cost_amount = fields.Float(string='Costo Mensual', compute='compute_cost_total', store=True)
    total_cost = fields.Float(string='Total Costo Hora', compute='compute_cost_total', store=True)
    invoice_id = fields.Many2one('account.move', string='Contabilización')

    @api.onchange('date_init', 'date_to')
    def onchange_date(self):
        for move in self:
            if move.date_init:
                date_init = str(move.date_init.year) + '-' + str(move.date_init.month).zfill(2) + '-' + '01'
                move.date_init = datetime.strptime(date_init, '%Y-%m-%d')
            if move.date_to:
                ultimo_de_mes = calendar.monthrange(move.date_to.year, move.date_to.month)
                move.date_to = str(move.date_to.year) + '-' + str(move.date_to.month).zfill(2) + '-' + str(
                    ultimo_de_mes[1])

    def action_draft(self):
        for machinery in self:
            machinery.write({'state': 'draft'})

    def action_costo(self):
        for machinery in self:
            machinery.write({'state': 'costo'})

    def action_cost_detail(self):
        for machinery in self:
            if machinery.real_cost_machinery_line:
                machinery.real_cost_machinery_line.unlink()
            account_moves = self.env['account.move.line'].search(
                [('analytic_distribution', 'in', [machinery.cost_id.id]),
                 ('date', '>=', machinery.date_init),
                 ('date', '<=', machinery.date_to)])
            if account_moves:
                lines = []
                for move in account_moves:
                    total_hrs = 0
                    machinery_id = False
                    implement_id = False
                    employee_id = False
                    labor_id = False
                    date = False
                    odometer_init = 0
                    odometer_end = 0
                    lrts_combustible = 0
                    # busqueda para saber si existe registros en horas
                    step_hr_m = self.env['step.hrs.machinery'].search(
                        [('invoice_id', '=', move.move_id.id)], limit=1)
                    if step_hr_m:
                        total_hrs = step_hr_m.hrs_machinery_line[0].hrs_maquina
                        machinery_id = step_hr_m.hrs_machinery_line[0].machinery_ids.id
                        implement_id = step_hr_m.hrs_machinery_line[0].implement_id.id
                        employee_id = step_hr_m.hrs_machinery_line[0].employee_id.id
                        labor_id = step_hr_m.hrs_machinery_line[0].labor_id.id
                        odometer_init = step_hr_m.hrs_machinery_line[0].odometer_init
                        odometer_end = step_hr_m.hrs_machinery_line[0].odometer_end
                        lrts_combustible = step_hr_m.hrs_machinery_line[0].lrts_combustible
                        date = move.move_id.date
                    new_line = (0, 0, {
                        'real_cost_id': machinery.id,
                        'name': move.name,
                        'date': date,
                        'machinery_ids': machinery_id,
                        'account_id': move.account_id.id,
                        'implement_id': implement_id,
                        'employee_id': employee_id,
                        'labor_id': labor_id,
                        # 'actividad_id': actividad_id,
                        # 'uom_id': uom_id,
                        'odometer_init': odometer_init,
                        'odometer_end': odometer_end,
                        'hrs_maquina': total_hrs,
                        'lrts_combustible': lrts_combustible,
                        'analytic_distribution': move.analytic_distribution,
                        'monto': move.debit,
                    })
                    lines.append(new_line)
                self.real_cost_machinery_line = lines
            # machinery.write({'state': 'draft'})

    def action_regist_detail(self):
        for machinery in self:
            if machinery.regist_cost_machinery_line:
                machinery.regist_cost_machinery_line.unlink()
            registry_moves = self.env['step.hrs.machinery'].search(
                [('temp_id', '=', machinery.temp_id.id),
                 # ('cost_id', '=', machinery.cost_id.id),
                 ('company_id', '=', machinery.company_id.id),
                 ('fundo_id', '=', machinery.fundo_id.id),
                 ('state', '=', 'done'),
                 ('date', '>=', machinery.date_init),
                 ('date', '<=', machinery.date_to)])
            if registry_moves:
                lines = []
                for line in registry_moves.hrs_machinery_line:
                    total_hrs = line.hrs_maquina
                    machinery_id = line.machinery_ids.id
                    implement_id = line.implement_id.id
                    employee_id = line.employee_id.id
                    labor_id = line.labor_id.id
                    odometer_init = line.odometer_init
                    odometer_end = line.odometer_end
                    lrts_combustible = line.lrts_combustible
                    date = line.date
                    new_line = (0, 0, {
                        'regist_cost_id': machinery.id,
                        # 'name': line.name,
                        'date': date,
                        'machinery_ids': machinery_id,
                        'implement_id': implement_id,
                        'employee_id': employee_id,
                        'cost_id': line.cost_id.id,
                        'labor_id': labor_id,
                        # 'actividad_id': actividad_id,
                        # 'uom_id': uom_id,
                        'odometer_init': odometer_init,
                        'odometer_end': odometer_end,
                        'hrs_maquina': total_hrs,
                        'lrts_combustible': lrts_combustible,
                    })
                    lines.append(new_line)
                self.regist_cost_machinery_line = lines
                self.compute_cost_total()
            # machinery.write({'state': 'draft'})

    def action_conta(self):
        for machinery in self:
            line_asiento = []
            total = 0.0
            invoice_id = self.env['account.move'].create([{
                'ref': self.name,
                'date': self.date,
                'move_type': 'entry',
                # 'contra': True,
                'state': 'draft',  # 'pro',
                # 'partner_id': machinery.partner_id.id,
                'journal_id': machinery.company_id.step_journal_machinery.id,
                # 'l10n_latam_document_type_id': machinery.company_id.step_document_type_id.id,
            }])
            machinery.invoice_id = invoice_id.id
            vals = []
            cost_temporada = self.env['step.temporada'].search(
                [('start_date', '<=', machinery.date),
                 ('end_date', '>=', machinery.date)], limit=1)
            for line in machinery.regist_cost_machinery_line:
                monto = float(machinery.total_cost) * float(line.hrs_maquina)
                debit_num_reg = {
                    # 'product_id': line.labor_id.product_id.id,
                    'name': 'Ref: ' + str(self.name),
                    'account_id': machinery.company_id.step_journal_machinery.default_account_id.id,
                    'debit': round(monto, 4),
                    'credit': 0,
                    'analytic_distribution': {str(machinery.temp_id.cost_id.id) + "," +
                                              str(line.cost_id.id) + "," +
                                              str(line.actividad_id.id): 100},
                    'move_id': invoice_id.id,
                    'tax_ids': False
                }
                # total = total + line.trato_total
                line_asiento.append(debit_num_reg)
                credit_num_reg = {
                    'name': 'Ref: ' + str(self.name),
                    'account_id': machinery.company_id.step_journal_machinery.account_control_ids[0].id,
                    'debit': 0,
                    'credit': round(monto, 4),
                    'move_id': invoice_id.id,
                    # 'analytic_distribution': {str(cost_temporada.cost_id.id) + "," +
                    #                           str(line.cost_id.cost_id.id) + "," +
                    #                           str(line.labor_id.actividad_id.id): 100},
                }
                line_asiento.append(credit_num_reg)
            create_line2 = self.env['account.move.line'].create(line_asiento)
            machinery.write({'state': 'conta'})

    def action_cost_create(self):
        for machinery in self:
            vals_analytic = {
                'name': '',
                'date': date.today(),
                'date_init': date.today(),
                'date_to': date.today(),
                'fundo_id': 1,
                'company_id': 1,
                'temp_id': 1,
                'responsable_id': 1,
                'cost_id': 'draft',
                'state': 'draft',
            }
            create_real_cost = self.env['real.cost.machinery'].create(vals_analytic)

    @api.model
    def create(self, vals):
        seq = str(self.env['ir.sequence'].next_by_code('step_hrs_machinery_seq'))
        vals["name"] = seq + '-' + str(vals["name"])
        return super(RealCostMachinery, self).create(vals)