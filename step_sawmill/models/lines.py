# -*- coding: utf-8 -*-
"""Líneas de detalle de Aserrío y Elaboración (producción, consumo y costos)."""
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class StepSawmillLineParent(models.AbstractModel):
    """Una línea cuelga de un Aserrío o de una Elaboración, nunca de ambos."""
    _name = 'step.sawmill.line.parent'
    _description = 'Padre de línea de proceso'
    _order = 'sequence, id'

    sequence = fields.Integer(default=10)
    sawing_id = fields.Many2one('step.sawmill.sawing', string='Aserrío', ondelete='cascade')
    elaboration_id = fields.Many2one('step.sawmill.elaboration', string='Elaboración',
                                     ondelete='cascade')

    @api.model_create_multi
    def create(self, vals_list):
        # @api.constrains no se dispara si ningún campo padre viene en vals.
        records = super().create(vals_list)
        records._check_single_parent()
        return records

    @api.constrains('sawing_id', 'elaboration_id')
    def _check_single_parent(self):
        for rec in self:
            if bool(rec.sawing_id) == bool(rec.elaboration_id):
                raise ValidationError(_(
                    'La línea debe pertenecer a un Aserrío o a una Elaboración (solo uno).'))


class StepSawmillOutputLine(models.Model):
    _name = 'step.sawmill.output.line'
    _inherit = 'step.sawmill.line.parent'
    _description = 'Producto obtenido'

    name = fields.Char(string='Tarjeta')
    product_id = fields.Many2one('product.product', string='Producto', required=True)
    uom_id = fields.Many2one('uom.uom', string='UdM')
    quantity = fields.Float(string='Cantidad UdM')
    pieces = fields.Integer(string='Cantidad piezas')
    quantity_m3 = fields.Float(string='Cantidad m³')
    thickness = fields.Float(string='Espesor')
    width = fields.Float(string='Ancho')
    quality_id = fields.Many2one('step.sawmill.quality', string='Calidad')
    grade_id = fields.Many2one('step.sawmill.grade', string='Grado')
    product_type_id = fields.Many2one('step.sawmill.product.type', string='Tipo de producto')
    destination_id = fields.Many2one('step.sawmill.destination', string='Destino')

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self.uom_id = self.product_id.uom_id


class StepSawmillInputLine(models.Model):
    _name = 'step.sawmill.input.line'
    _inherit = 'step.sawmill.line.parent'
    _description = 'Materia prima consumida'

    product_id = fields.Many2one('product.product', string='Producto', required=True)
    uom_id = fields.Many2one('uom.uom', string='UdM')
    lot_id = fields.Many2one('stock.lot', string='Lote')
    tarja = fields.Char(string='Tarja')
    diameter = fields.Float(string='Diámetro')
    quantity = fields.Float(string='Cantidad UdM')
    pieces = fields.Float(string='Cantidad piezas')
    unit_cost = fields.Float(string='Costo unitario')
    total_cost = fields.Float(string='Costo total', compute='_compute_total_cost', store=True)

    @api.depends('quantity', 'unit_cost')
    def _compute_total_cost(self):
        for rec in self:
            rec.total_cost = rec.quantity * rec.unit_cost

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self.uom_id = self.product_id.uom_id


class StepSawmillCostLine(models.Model):
    _name = 'step.sawmill.cost.line'
    _inherit = 'step.sawmill.line.parent'
    _description = 'Valorización por producto'

    product_id = fields.Many2one('product.product', string='Producto', required=True)
    uom_id = fields.Many2one('uom.uom', string='UdM')
    quantity = fields.Float(string='Cantidad')
    pieces = fields.Float(string='Piezas')
    cost_raw = fields.Float(string='Costo MP')
    cost_own_labor = fields.Float(string='Costo MO propia')
    cost_contract_labor = fields.Float(string='Costo MO terceros')
    cost_supplies = fields.Float(string='Costo insumos')
    cost_expenses = fields.Float(string='Costo gastos y servicios')
    cost_machines = fields.Float(string='Costo máquinas')
    cost_total = fields.Float(string='Costo total', compute='_compute_costs', store=True)
    portion = fields.Float(string='Porción producto')
    unit_cost_uom = fields.Float(string='Costo unit. UdM', compute='_compute_costs', store=True)
    unit_cost_piece = fields.Float(string='Costo unit. pieza', compute='_compute_costs', store=True)

    @api.depends('cost_raw', 'cost_own_labor', 'cost_contract_labor', 'cost_supplies',
                 'cost_expenses', 'cost_machines', 'quantity', 'pieces')
    def _compute_costs(self):
        for rec in self:
            total = (rec.cost_raw + rec.cost_own_labor + rec.cost_contract_labor
                     + rec.cost_supplies + rec.cost_expenses + rec.cost_machines)
            rec.cost_total = total
            rec.unit_cost_uom = total / rec.quantity if rec.quantity else 0.0
            rec.unit_cost_piece = total / rec.pieces if rec.pieces else 0.0

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self.uom_id = self.product_id.uom_id
