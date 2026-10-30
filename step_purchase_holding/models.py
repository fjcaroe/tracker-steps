from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    step_delivery_company_ids = fields.Many2many('res.company', compute='_compute_step_delivery_companies')
    step_branch_delivery_address_id = fields.Many2one(
        related='picking_type_id.warehouse_id.company_id.partner_id', string='Dirección de entrega', readonly=True)

    @api.depends('company_id')
    @api.depends_context('allowed_company_ids')
    def _compute_step_delivery_companies(self):
        for order in self:
            root = order.company_id.root_id
            order.step_delivery_company_ids = self.env.companies.filtered(lambda company: company.root_id == root)

    def _step_check_delivery_company(self, origin, destination):
        if destination and destination != origin:
            if destination not in self.env.companies or destination.root_id != origin.root_id:
                raise ValidationError(_('Seleccione una sucursal de la misma empresa que esté habilitada en sus compañías activas.'))

    @api.onchange('picking_type_id')
    def _onchange_step_delivery_branch(self):
        for order in self:
            destination = order.picking_type_id.warehouse_id.company_id
            if destination and destination != order.company_id:
                order._step_check_delivery_company(order.company_id, destination)
                if order.state not in ('draft', 'sent') or order.order_line:
                    raise UserError(_('Seleccione la sucursal de entrega antes de agregar productos al pedido.'))
                order.company_id = destination
                order._onchange_company_id()

    @api.model_create_multi
    def create(self, vals_list):
        normalized = []
        for values in vals_list:
            values = dict(values)
            if values.get('picking_type_id'):
                operation = self.env['stock.picking.type'].browse(values['picking_type_id'])
                operation.check_access('read')
                destination = operation.warehouse_id.company_id
                origin = self.env['res.company'].browse(values.get('company_id')) or self.env.company
                self._step_check_delivery_company(origin, destination)
                if destination:
                    values['company_id'] = destination.id
            normalized.append(values)
        return super().create(normalized)

    def write(self, vals):
        if vals.get('picking_type_id'):
            operation = self.env['stock.picking.type'].browse(vals['picking_type_id'])
            operation.check_access('read')
            destination = operation.warehouse_id.company_id
            for order in self:
                origin = self.env['res.company'].browse(vals.get('company_id')) or order.company_id
                order._step_check_delivery_company(origin, destination)
                if destination and destination != order.company_id:
                    if order.state not in ('draft', 'sent') or order.order_line:
                        raise UserError(_('Seleccione la sucursal de entrega antes de agregar productos al pedido.'))
                    # Preserve native company-dependent pricing/taxes: the destination
                    # is fixed before the first purchase line is entered.
                    return super(PurchaseOrder, order).write(dict(vals, company_id=destination.id)) if len(self)==1 else self._step_write_individually(vals)
        return super().write(vals)

    def _step_write_individually(self, vals):
        for order in self:
            order.write(vals)
        return True

    @api.constrains('company_id', 'picking_type_id')
    def _check_step_branch_ownership(self):
        for order in self:
            destination = order.picking_type_id.warehouse_id.company_id
            if destination and destination != order.company_id:
                raise ValidationError(_('El pedido y la operación de recepción deben pertenecer a la misma sucursal.'))
