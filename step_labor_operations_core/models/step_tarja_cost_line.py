# © 2025 (Jamie Escalante <jamie.escalante7@gmail.com>)
# -*- coding: utf-8 -*-

import base64
from odoo import api, fields, models, tools, SUPERUSER_ID, _, Command
from odoo.exceptions import UserError, RedirectWarning, ValidationError


class StepTarjaCostLine(models.Model):
    _name = 'step.tarja.cost.line'
    _rec_name = 'employee_id'

    @api.depends('employee_id', 'quantity', 'tarifa', 'cost_id', 'labor_id')
    def compute_total_trato(self):
        eta_list = []
        hora_extra = 0
        for move in self:
            min_quantity = 0
            if move.tarja_cost_id.pricelist_id:
                if move.tarja_cost_id.pricelist_id.cost_ids:
                    move.cost_id_domain = self.env['account.analytic.account'].search(
                        [('id', 'in', move.tarja_cost_id.pricelist_id.cost_ids.ids)]).ids
                for item in move.tarja_cost_id.pricelist_id.item_ids:
                    if move.labor_id.id == item.product_tmpl_id.id:
                        move.cant_minima = item.min_quantity
                        move.tarifa = item.fixed_price
                        move.uom_id = item.uom_id.id
            # move.cost_id_domain = self.env['account.analytic.account'].search(
            #     [('fundo_id', 'in', [move.tarja_cost_id.fundo_id.id]),
            #      ('especie_id', 'in', [move.tarja_cost_id.especie_id.id]),
            #      ('grupo_variedad_id', 'in',
            #       move.tarja_cost_id.grupo_variedad_id_domain.ids)]).ids
            move.employee_id_domain = self.env['hr.employee'].search(
                [('is_contratista', '=', True)]).ids
            move.trato_total = float(move.quantity) * float(move.tarifa)
            if not move.cost_id_domain:
                move.cost_id_domain = []

    employee_id = fields.Many2one('hr.employee', 'Empleado')
    employee_id_domain = fields.Many2many('hr.employee', 'tarja_employee_rel', 'employee_id',
                                      'tarja_id', string='Empleados', compute='compute_total_trato')
    partner_id = fields.Many2one(related='employee_id.contratista_id', string='Contratista')
    tarja_cost_id = fields.Many2one(
        comodel_name='step.tarja',
        string="tarja Reference",
        required=True, ondelete='cascade', index=True, copy=False)
    cost_id = fields.Many2one(
        'account.analytic.account', "Centro costos",
    )
    cost_id_domain = fields.Many2many('account.analytic.account', 'tarja_cost_rel', 'cost_id',
                                             'tarja_id', string='Centro costos', compute='compute_total_trato', store=True)
    labor_id = fields.Many2one('product.template', 'Labor/Tarea', required=False)
    uom_id = fields.Many2one('uom.uom', string='UdM', required=False)
    quantity = fields.Float(string='Cantidad')
    hrs = fields.Float(string='Hrs. Ord.')
    cant_minima = fields.Float(string='Cant Minima')
    tarifa = fields.Float(string='Tarifa')
    trato_total = fields.Float(string='Total Trato', compute='compute_total_trato', store=True)
    # informes
    parent_name = fields.Char(related='tarja_cost_id.name', string='Nombre')
    salary_id = fields.Many2one(related='tarja_cost_id.salary_id', string="Cuadrilla")
    salary_id_contrac = fields.Many2one(related='tarja_cost_id.salary_id_contrac', string="Cuadrilla Contratista")
    tarja_type = fields.Selection(related='tarja_cost_id.tarja_type', string='Tipo Tarea')
    partner_id = fields.Many2one(related='tarja_cost_id.partner_id', string='Contratista')
    folio = fields.Char(related='tarja_cost_id.folio', string='Orden de Trabajo')
    date = fields.Date(related='tarja_cost_id.date', string='Fecha')
    user_id = fields.Many2one(related='tarja_cost_id.user_id', string='Usuario')
    fundo_id = fields.Many2one(related='tarja_cost_id.fundo_id', string="Fundo")
    super_id = fields.Many2one(related='tarja_cost_id.super_id', string='Supervisor')
    auto_id = fields.Many2one(related='tarja_cost_id.auto_id', string='Autorizador')
    company_id = fields.Many2one(related='tarja_cost_id.company_id', string='Empresa')
    state = fields.Selection(related='tarja_cost_id.state', string='Estado')
    gratificacion_legal = fields.Boolean(related='tarja_cost_id.gratificacion_legal')
    sema_corrida_legal = fields.Boolean(related='tarja_cost_id.sema_corrida_legal')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('employee_id'):
                tarja = self.env['step.tarja'].browse(vals['tarja_cost_id'])
                exist = self.env['step.tarja.cost.line'].search(
                    [('employee_id', '=', vals['employee_id']), ('date', '=', tarja.date)])
                if exist:
                    employee = self.env['hr.employee'].browse(vals['employee_id'])
                    raise UserError(
                        _("El Empleado %s ya posee un Registro para la fecha %s", employee.name, tarja.date))
        return super(StepTarjaCostLine, self).create(vals_list)