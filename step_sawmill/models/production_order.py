# -*- coding: utf-8 -*-
from odoo import api, fields, models


class StepSawmillProductionStage(models.Model):
    _name = 'step.sawmill.production.stage'
    _description = 'Etapa de orden de producción'
    _order = 'sequence, id'

    name = fields.Char(string='Etapa', required=True, translate=True)
    sequence = fields.Integer(default=10)
    fold = fields.Boolean(string='Plegada en kanban')


class StepSawmillProductionOrder(models.Model):
    _name = 'step.sawmill.production.order'
    _description = 'Orden de producción de Aserradero'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'scheduled_date desc, id desc'

    name = fields.Char(string='Descripción', required=True, tracking=True)
    number = fields.Char(string='Número OP', copy=False, readonly=True, default='Nuevo')
    user_id = fields.Many2one('res.users', string='Responsable',
                              default=lambda self: self.env.user, tracking=True)
    company_id = fields.Many2one('res.company', string='Empresa', required=True,
                                 default=lambda self: self.env.company)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id')
    scheduled_date = fields.Date(string='Fecha programada')
    date_start = fields.Datetime(string='Fecha OP')
    date_stop = fields.Datetime(string='Fecha de finalización')
    stage_id = fields.Many2one(
        'step.sawmill.production.stage', string='Etapa', tracking=True,
        group_expand='_read_group_stage_ids', copy=False,
        default=lambda self: self.env['step.sawmill.production.stage'].search([], limit=1))
    kanban_state = fields.Selection(
        [('normal', 'En progreso'), ('done', 'Listo'), ('blocked', 'Bloqueado')],
        string='Estado kanban', default='normal')
    priority = fields.Boolean(string='Alta prioridad')
    color = fields.Integer(string='Color')
    value = fields.Monetary(string='Valor')
    notes = fields.Html(string='Notas')
    line_ids = fields.One2many('step.sawmill.production.order.line', 'order_id', string='Productos')
    work_order_ids = fields.One2many('step.sawmill.work.order', 'production_order_id',
                                     string='Órdenes de trabajo')
    work_order_count = fields.Integer(compute='_compute_work_order_count')

    @api.model
    def _read_group_stage_ids(self, stages, domain):
        return stages.search([], order='sequence, id')

    @api.depends('work_order_ids')
    def _compute_work_order_count(self):
        for rec in self:
            rec.work_order_count = len(rec.work_order_ids)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('number') or vals.get('number') == 'Nuevo':
                vals['number'] = self.env['ir.sequence'].next_by_code(
                    'step.sawmill.production.order') or 'Nuevo'
        return super().create(vals_list)

    def action_view_work_orders(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id(
            'step_sawmill.action_step_sawmill_work_order')
        action['domain'] = [('production_order_id', '=', self.id)]
        action['context'] = {'default_production_order_id': self.id}
        return action


class StepSawmillProductionOrderLine(models.Model):
    _name = 'step.sawmill.production.order.line'
    _description = 'Línea de orden de producción de Aserradero'
    _order = 'sequence, id'

    order_id = fields.Many2one('step.sawmill.production.order', required=True, ondelete='cascade')
    sequence = fields.Integer(default=10)
    product_id = fields.Many2one('product.product', string='Producto', required=True)
    quantity = fields.Float(string='Cantidad', default=1.0)
    uom_id = fields.Many2one('uom.uom', string='UdM')
    notes = fields.Char(string='Notas')

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self.uom_id = self.product_id.uom_id


class StepSawmillWorkOrder(models.Model):
    _name = 'step.sawmill.work.order'
    _description = 'Orden de trabajo de Aserradero'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'

    name = fields.Char(string='Descripción', required=True, tracking=True)
    number = fields.Char(string='Folio OT', copy=False, readonly=True, default='Nuevo')
    production_order_id = fields.Many2one('step.sawmill.production.order',
                                          string='Orden de producción', tracking=True)
    company_id = fields.Many2one('res.company', string='Empresa', required=True,
                                 default=lambda self: self.env.company)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id')
    date = fields.Date(string='Fecha', default=fields.Date.context_today)
    date_start = fields.Datetime(string='Fecha de inicio')
    date_stop = fields.Datetime(string='Fecha de finalización')
    kanban_state = fields.Selection(
        [('normal', 'En progreso'), ('done', 'Listo'), ('blocked', 'Bloqueado')],
        string='Estado kanban', default='normal', tracking=True)
    value = fields.Monetary(string='Valor')
    notes = fields.Html(string='Notas')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('number') or vals.get('number') == 'Nuevo':
                vals['number'] = self.env['ir.sequence'].next_by_code(
                    'step.sawmill.work.order') or 'Nuevo'
        return super().create(vals_list)
