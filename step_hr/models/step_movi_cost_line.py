# © 2025 (Jamie Escalante <jamie.escalante7@gmail.com>)
# -*- coding: utf-8 -*-

import base64
from odoo import api, fields, models, tools, SUPERUSER_ID, _, Command


class StepMoviCostLine(models.Model):
    _name = 'step.movi.cost.line'
    _rec_name = 'employee_id'

    employee_id = fields.Many2one('hr.employee', 'Empleado')
    movi_id = fields.Many2one(
        comodel_name='step.movi.registry',
        string="Movimiento",
        required=True, ondelete='cascade', index=True, copy=False)
    cod_nip = fields.Char(related='employee_id.pin', string='Código NIP')
    recorrido_ent = fields.Char('Recorrido Entrada', required=False)
    recorrido_sal = fields.Char('Recorrido Salida', required=False)
    cost_in = fields.Float(string='Costo Entrada')
    cost_out = fields.Float(string='Costo Salida')
    cost_total = fields.Float(string='Costo Trabajador')
    cost_id = fields.Many2one(
        'account.analytic.account', "Centro costos",
    )
    labor_id = fields.Many2one('product.template', 'Labor/Tarea', required=False)
    # informes
    parent_name = fields.Char(related='movi_id.name', string='Nombre')
    date = fields.Datetime(related='movi_id.date', string='Fecha')
    fundo_id = fields.Many2one(related='movi_id.fundo_id', string="Fundo")
    recorrido_id = fields.Many2one(related='movi_id.recorrido_id', string='Recorrido')
    vehicle_id = fields.Many2one(related='movi_id.vehicle_id', string='Vehículo')
    responsable_id = fields.Many2one(related='movi_id.responsable_id', string='Responsable')
    partner_id = fields.Many2one(related='movi_id.partner_id', string='Transportista')
    chofer_id = fields.Many2one(related='movi_id.chofer_id', string='Chofer')
    pricelist_id = fields.Many2one(related='movi_id.pricelist_id', string='Lista de tarifa')
    company_id = fields.Many2one(related='movi_id.company_id', string='Empresa')
    note = fields.Html(related='movi_id.note', string="Notas")
    state = fields.Selection(related='movi_id.state', string='Estado')
    invoice_id = fields.Many2one(related='movi_id.invoice_id', string='Contabilización')