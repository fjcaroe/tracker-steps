from odoo import _, api, fields, models, Command
from odoo.exceptions import UserError, ValidationError


class Picking(models.Model):
    _inherit = 'stock.picking'

    production_order_id = fields.Many2one('step.management.production.order', string='OP vigente',
        check_company=True, copy=False, domain="[('company_id','=',company_id), ('state','=','authorized')]")

    @api.onchange('production_order_id')
    def _onchange_production_order(self):
        self.num_op = self.production_order_id.name if self.production_order_id else False

    @api.constrains('production_order_id', 'company_id')
    def _check_production_order(self):
        for picking in self.filtered('production_order_id'):
            if picking.production_order_id.state != 'authorized':
                raise ValidationError(_("Seleccione una OP autorizada y vigente."))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('production_order_id'):
                vals['num_op'] = self.env['step.management.production.order'].browse(vals['production_order_id']).name
        return super().create(vals_list)

    def write(self, vals):
        if 'production_order_id' in vals:
            vals = dict(vals, num_op=self.env['step.management.production.order'].browse(vals['production_order_id']).name if vals['production_order_id'] else False)
        return super().write(vals)

    def action_create_dispatch_guide(self):
        self.ensure_one()
        if self.state == 'cancel':
            raise UserError(_("No se puede crear una guía desde una operación cancelada."))
        action = super().action_create_dispatch_guide()
        lines = []
        kg = self.env.ref('uom.product_uom_kgm')
        for move in self.move_ids.filtered(lambda m: m.state != 'cancel'):
            quantity = move.quantity if self.state == 'done' else move.product_uom_qty
            if quantity <= 0:
                continue
            if move.product_uom.category_id == kg.category_id:
                kilos = move.product_uom._compute_quantity(quantity, kg, round=False)
            else:
                kilos = move.product_uom._compute_quantity(quantity, move.product_id.uom_id, round=False) * move.product_id.weight
            lines.append(Command.create({'product_id': move.product_id.id,
                'description': move.description_picking or move.product_id.display_name,
                'product_uom_id': move.product_uom.id, 'quantity': quantity, 'quantity_kg': kilos}))
        if not lines:
            raise UserError(_("No hay cantidades para despachar en esta operación."))
        warehouse_partner = self.picking_type_id.warehouse_id.partner_id
        action['context'].update({
            'default_company_id': self.company_id.id,
            'default_reference': ' / '.join(filter(None, [self.name, self.num_op, self.num_ot])),
            'default_origin_address': warehouse_partner.contact_address or self.company_id.partner_id.contact_address or self.location_id.complete_name,
            'default_line_ids': lines})
        return action
