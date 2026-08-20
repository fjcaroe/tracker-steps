# © 2025 (Jamie Escalante <jamie.escalante7@gmail.com>)
# -*- coding: utf-8 -*-

import base64
from odoo import api, fields, models, tools, SUPERUSER_ID, _, Command


class StepCosechaTarjaRegistryLine(models.Model):
    _name = 'step.cosecha.tarja.registry.line'
    # _rec_name = 'employee_id'

    # @api.depends('employee_id', 'quantity', 'tarifa')
    # def compute_total_trato(self):
    #     eta_list = []
    #     hora_extra = 0
    #     self.trato_total = 0
    #     # for move in self:
    #     #     min_quantity = 0
    #     #     if move.tarja_cost_id.pricelist_id:
    #     #         for item in move.tarja_cost_id.pricelist_id.item_ids:
    #     #             if move.labor_id.product_id == item.product_tmpl_id:
    #     #                 move.cant_minima = item.min_quantity
    #     #                 move.tarifa = item.fixed_price
    #     #     move.cost_id_domain = self.env['step.centro.costo'].search(
    #     #         [('fundo_id', '=', move.tarja_cost_id.fundo_id.id),
    #     #          ('especie_id', '=', move.tarja_cost_id.especie_id.id),
    #     #          ('grupo_variedad_id', '=',
    #     #           move.tarja_cost_id.grupo_variedad_id.id)]).ids
    #     #     move.employee_id_domain = self.env['hr.employee'].search(
    #     #         [('is_contratista', '=', True),
    #     #          ('contratista_id', '=',
    #     #           move.tarja_cost_id.partner_id.id)]).ids
    #     #     move.trato_total = float(move.quantity) * float(move.tarifa)
    #
    # employee_id = fields.Many2one('hr.employee', 'Empleado')
    # employee_id_domain = fields.Many2many('hr.employee', 'cosecha_employee_rel', 'employee_id',
    #                                       'cosecha_id', string='Empleados', compute='compute_total_trato')

    employee_id = fields.Many2one('hr.employee', 'Empleado')
    # employee_id_domain = fields.Many2many('hr.employee', 'cosecha_employee_rel', 'employee_id',
    #                                       'cosecha_id', string='Empleados', compute='compute_total_trato')
    registry_id = fields.Many2one(
        comodel_name='step.cosecha.registry',
        string="Cosecha",
        required=True, ondelete='cascade', index=True, copy=False)
    cod_nip = fields.Char(related='employee_id.pin', string='Código NIP')
    num_tarja = fields.Char(string='N° Tarja')
    date_tarja = fields.Datetime(string='Fecha hora tarja')
    qty_caja = fields.Float(string='Cantidad Cj')
    qty_kg = fields.Float(string='Cantidad Kg')
    quantity = fields.Float(string='Cantidad')
    hrs = fields.Float(string='Hrs. Ord.')
    cant_minima = fields.Float(string='Cant Minima')
    tarifa = fields.Float(string='Tarifa')
    trato_total = fields.Float(string='Total Trato')