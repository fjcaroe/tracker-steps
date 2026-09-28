# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class StepSawmillDrying(models.Model):
    _name = 'step.sawmill.drying'
    _description = 'Secado'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'process_date desc, id desc'

    name = fields.Char(string='Descripción', required=True, tracking=True)
    state = fields.Selection(
        [('in_process', 'En proceso'), ('done', 'Terminado')],
        string='Estado', default='in_process', required=True, copy=False, tracking=True)
    company_id = fields.Many2one('res.company', string='Empresa', required=True,
                                 default=lambda self: self.env.company)
    process_date = fields.Date(string='Fecha proceso', default=fields.Date.context_today)
    work_order_id = fields.Many2one('step.sawmill.work.order', string='Orden de trabajo')
    workcenter_id = fields.Many2one('mrp.workcenter', string='Centro de trabajo')
    supervisor_id = fields.Many2one('hr.employee', string='Supervisor')
    load_operator_id = fields.Many2one('hr.employee', string='Operador de carga')
    unload_operator_id = fields.Many2one('hr.employee', string='Operador de descarga')
    orientation = fields.Selection([
        ('wet', 'Húmedo'),
        ('raw_elaboration', 'MP Elaboración'),
        ('raw_impregnation', 'MP Impregnación'),
        ('raw_drying', 'MP Secado'),
        ('service', 'Servicio'),
    ], string='Orientación')
    wood_category = fields.Char(string='Categoría madera')
    quantity_inches = fields.Float(string='Cantidad pulgadas')
    program = fields.Char(string='Programa secado')
    machine = fields.Char(string='Máquina')
    cycle = fields.Integer(string='Ciclo')
    cycle_hours = fields.Float(string='Horas del ciclo')
    pause_hours = fields.Float(string='Horas de pausa')
    cooling_hours = fields.Float(string='Horas enfriamiento')
    estimated_hours = fields.Float(string='Duración estimada (hrs)')
    date_start = fields.Datetime(string='Fecha-hora inicial')
    date_stop = fields.Datetime(string='Fecha-hora final')
    real_hours = fields.Float(string='Duración real (hrs)', compute='_compute_real_hours',
                              store=True, readonly=False)
    line_ids = fields.One2many('step.sawmill.drying.line', 'drying_id', string='Cargas')

    @api.depends('date_start', 'date_stop')
    def _compute_real_hours(self):
        for rec in self:
            if rec.date_start and rec.date_stop and rec.date_stop >= rec.date_start:
                rec.real_hours = (rec.date_stop - rec.date_start).total_seconds() / 3600.0
            else:
                rec.real_hours = rec.real_hours or 0.0

    def action_done(self):
        if any(rec.state != 'in_process' for rec in self):
            raise UserError(_('Solo se puede terminar un secado En proceso.'))
        self.write({'state': 'done'})

    def action_reopen(self):
        self.write({'state': 'in_process'})


class StepSawmillDryingLine(models.Model):
    _name = 'step.sawmill.drying.line'
    _description = 'Carga de secado'
    _order = 'sequence, id'

    drying_id = fields.Many2one('step.sawmill.drying', required=True, ondelete='cascade')
    sequence = fields.Integer(default=10)
    name = fields.Char(string='Línea')
    tarja = fields.Char(string='Tarjeta')
    tarja_date = fields.Date(string='Fecha tarjeta')
    origin = fields.Char(string='Origen')
    wood_category = fields.Char(string='Categoría madera')
    product_id = fields.Many2one('product.product', string='Producto')
    uom_id = fields.Many2one('uom.uom', string='UdM')
    quality_id = fields.Many2one('step.sawmill.quality', string='Calidad')
    thickness = fields.Float(string='Espesor')
    width = fields.Float(string='Ancho')
    length = fields.Float(string='Largo')
    pieces = fields.Float(string='Cantidad piezas')
    quantity_inches = fields.Float(string='Cantidad pulgadas')

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self.uom_id = self.product_id.uom_id
