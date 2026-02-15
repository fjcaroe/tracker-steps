# © 2025 (Jamie Escalante <jamie.escalante7@gmail.com>)
# -*- coding: utf-8 -*-

import base64
from odoo import api, fields, models, tools, SUPERUSER_ID, _, Command


class StepCosechaTarjaLine(models.Model):
    _name = 'step.cosecha.tarja.line'
    _rec_name = 'employee_id'

    @api.depends('employee_id', 'quantity', 'tarifa')
    def compute_total_trato(self):
        eta_list = []
        hora_extra = 0
        for move in self:
            min_quantity = 0
            if move.registry_id.pricelist_id:
                for item in move.registry_id.pricelist_id.item_ids:
                    if move.registry_id.labor_id.id == item.product_tmpl_id.id:
                        move.cant_minima = item.min_quantity
                        move.tarifa = item.fixed_price
                        # move.uom_id = item.uom_id.id
            move.cost_id_domain = self.env['account.analytic.account'].search(
                [('fundo_id', '=', move.registry_id.fundo_id.id),
                 ('especie_id', '=', move.registry_id.especie_id.id),
                 ('grupo_variedad_id', 'in',
                  move.registry_id.grupo_variedad_id_domain.ids)]).ids
            move.employee_id_domain = self.env['hr.employee'].search(
                [('is_contratista', '=', True),
                 ('contratista_id', '=',
                  move.registry_id.partner_id.id)]).ids
            move.trato_total = float(move.quantity) * float(move.tarifa)

    employee_id = fields.Many2one('hr.employee', 'Empleado')
    employee_id_domain = fields.Many2many('hr.employee', 'cost_employee_rel', 'employee_id',
                                          'cost_id', string='Empleados', compute='compute_total_trato', store=True)
    registry_id = fields.Many2one(
        comodel_name='step.cosecha.registry',
        string="Cosecha Reference",
        required=True, ondelete='cascade', index=True, copy=False)
    cost_id = fields.Many2one(
        'account.analytic.account', "Centro costos",
    )
    cost_id_domain = fields.Many2many('account.analytic.account', 'cosecha_cost_rel', 'cost_id',
                                      'cost_id', string='Centro costos', compute='compute_total_trato', store=True)
    labor_id = fields.Many2one('product.template', 'Labor/Tarea', required=False)
    uom_id = fields.Many2one('uom.uom', string='UdM', required=False)
    quantity = fields.Float(string='Cantidad')
    hrs = fields.Float(string='Hrs. Ord.')
    cant_minima = fields.Float(string='Cant Minima')
    tarifa = fields.Float(string='Tarifa')
    trato_total = fields.Float(string='Total Trato', compute='compute_total_trato', store=True)