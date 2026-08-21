# © 2025 (Jamie Escalante <jamie.escalante7@gmail.com>)
# -*- coding: utf-8 -*-

import base64
from odoo import api, fields, models, tools, SUPERUSER_ID, _, Command


class StepCosechaTarjaLine(models.Model):
    _name = 'step.cosecha.tarja.line'
    _rec_name = 'employee_id'

    @api.depends(
        'employee_id', 'quantity', 'tarifa', 'labor_id', 'uom_id',
        'registry_id.pricelist_id', 'registry_id.date',
        'registry_id.fundo_id', 'registry_id.especie_id',
        'registry_id.grupo_variedad_id_domain', 'registry_id.partner_id'
    )
    def compute_total_trato(self):
        for move in self:
            registry = move.registry_id
            move.cost_id_domain = self.env['account.analytic.account']
            move.employee_id_domain = self.env['hr.employee']
            move.trato_total = 0.0
            if not registry:
                continue

            labor = move.labor_id or registry.labor_id
            if registry.pricelist_id and labor:
                item, unit_price = registry._get_cosecha_unit_price(
                    labor, move.quantity, move.uom_id
                )
                if item:
                    move.cant_minima = item.min_quantity
                    move.tarifa = unit_price
                    if item.uom_id:
                        move.uom_id = item.uom_id
            move.cost_id_domain = self.env['account.analytic.account'].search(
                [('fundo_id', '=', registry.fundo_id.id),
                 ('especie_id', '=', registry.especie_id.id),
                 ('grupo_variedad_id', 'in',
                  registry.grupo_variedad_id_domain.ids)])
            move.employee_id_domain = self.env['hr.employee'].search(
                [('is_contratista', '=', True),
                 ('contratista_id', '=',
                  registry.partner_id.id)])
            move.trato_total = float(move.quantity) * float(move.tarifa)

    employee_id = fields.Many2one('hr.employee', 'Empleado')
    employee_id_domain = fields.Many2many('hr.employee', 'cost_employee_rel', 'employee_id',
                                          'cost_id', string='Empleados', compute='compute_total_trato')
    registry_id = fields.Many2one(
        comodel_name='step.cosecha.registry',
        string="Cosecha Reference",
        required=True, ondelete='cascade', index=True, copy=False)
    cost_id = fields.Many2one(
        'account.analytic.account', "Centro costos",
    )
    cost_id_domain = fields.Many2many('account.analytic.account', 'cost_cost_rel', 'cost_id',
                                      'cost_id', string='Centro costos', compute='compute_total_trato')
    labor_id = fields.Many2one('product.template', 'Labor/Tarea', required=False)
    uom_id = fields.Many2one('uom.uom', string='UdM', required=False)
    quantity = fields.Float(string='Cantidad')
    hrs = fields.Float(string='Hrs. Ord.')
    cant_minima = fields.Float(string='Cant Minima')
    tarifa = fields.Float(string='Tarifa')
    trato_total = fields.Float(string='Total Trato', compute='compute_total_trato')
