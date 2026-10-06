# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class StepSawmillImpregnation(models.Model):
    _name = 'step.sawmill.impregnation'
    _description = 'Impregnado'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'process_date desc, id desc'

    name = fields.Char(string='Hoja de carga', required=True, tracking=True)
    state = fields.Selection(
        [('draft', 'Ingresado'), ('approved', 'Aprobado'), ('certified', 'Certificado')],
        string='Estado', default='draft', required=True, copy=False, tracking=True)
    company_id = fields.Many2one('res.company', string='Empresa', required=True,
                                 default=lambda self: self.env.company)
    process_date = fields.Date(string='Fecha proceso', default=fields.Date.context_today)
    work_order_id = fields.Many2one('step.sawmill.work.order', string='Orden de trabajo')
    workcenter_id = fields.Many2one('mrp.workcenter', string='Centro de trabajo')
    operator_id = fields.Many2one('hr.employee', string='Operador')
    tank = fields.Char(string='Estanque')
    preservative = fields.Char(string='Preservante')
    wood_category = fields.Char(string='Categoría madera')
    product_id = fields.Many2one('product.product', string='Producto a impregnar')
    quantity_m3 = fields.Float(string='Cantidad m³')
    date_start = fields.Datetime(string='Fecha-hora inicial')
    date_stop = fields.Datetime(string='Fecha-hora final')
    total_time = fields.Float(string='Tiempo total (hrs)', compute='_compute_total_time',
                              store=True, readonly=False)
    # Valores objetivo (teóricos)
    retention_target = fields.Float(string='Retención St kg/m³')
    concentration = fields.Float(string='Concentración preservante (%)')
    absorption_target = fields.Float(string='Absorción St lt/m³')
    absorption_total_target = fields.Float(string='Absorción total St lt')
    consumption_target = fields.Float(string='Consumo St preservante')
    # Mediciones reales
    tank_level_initial = fields.Float(string='Nivel estanque inicial')
    tank_level_final = fields.Float(string='Nivel estanque final')
    consumption_total_real = fields.Float(string='Consumo total real', required=True, default=0.0)
    absorption_real = fields.Float(string='Absorción real lt/m³')
    retention_real = fields.Float(string='Retención real kg/m³')
    consumption_real = fields.Float(string='Consumo real preservante')
    line_ids = fields.One2many('step.sawmill.impregnation.line', 'impregnation_id',
                               string='Tarjas impregnadas')

    @api.depends('date_start', 'date_stop')
    def _compute_total_time(self):
        for rec in self:
            if rec.date_start and rec.date_stop and rec.date_stop >= rec.date_start:
                rec.total_time = (rec.date_stop - rec.date_start).total_seconds() / 3600.0
            else:
                rec.total_time = rec.total_time or 0.0

    def action_approve(self):
        if any(rec.state != 'draft' for rec in self):
            raise UserError(_('Solo se puede aprobar un Impregnado Ingresado.'))
        self.write({'state': 'approved'})

    def action_certify(self):
        if any(rec.state != 'approved' for rec in self):
            raise UserError(_('Solo se puede certificar un Impregnado Aprobado.'))
        self.write({'state': 'certified'})

    def action_reset(self):
        self.write({'state': 'draft'})


class StepSawmillImpregnationLine(models.Model):
    _name = 'step.sawmill.impregnation.line'
    _description = 'Tarja impregnada'
    _order = 'sequence, id'

    impregnation_id = fields.Many2one('step.sawmill.impregnation', required=True, ondelete='cascade')
    sequence = fields.Integer(default=10)
    name = fields.Char(string='Tarjeta')
    product_id = fields.Many2one('product.product', string='Producto')
    uom_id = fields.Many2one('uom.uom', string='UdM')
    product_category_id = fields.Many2one('product.category', string='Categoría producto')
    pieces = fields.Float(string='Cantidad piezas')
    quantity_inches = fields.Float(string='Cantidad pulgadas')
    quantity_m3 = fields.Float(string='Cantidad m³')

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self.uom_id = self.product_id.uom_id
            self.product_category_id = self.product_id.categ_id
