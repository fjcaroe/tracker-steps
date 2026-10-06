"""Immutable versions of the packing instruction used by stock reservations."""
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

_APPROVAL = object()


class PackingInstruction(models.Model):
    _name = 'step.packing.instruction'
    _description = 'Versión de instructivo de embalaje'
    _order = 'order_id, version desc'
    order_id = fields.Many2one('step.packing.order', string='OP', required=True, ondelete='restrict')
    company_id = fields.Many2one(related='order_id.company_id', store=True)
    name = fields.Char('Referencia', required=True)
    version = fields.Integer('Versión', readonly=True, required=True, default=1)
    instruction = fields.Html('Instrucciones', required=True)
    state = fields.Selection([('draft', 'Borrador'), ('approved', 'Aprobado')], default='draft', required=True, copy=False)
    approved_by = fields.Many2one('res.users', readonly=True, copy=False)
    approved_at = fields.Datetime(readonly=True, copy=False)
    _sql_constraints = [('order_version_unique', 'unique(order_id, version)', 'La versión ya existe para la OP.')]

    @api.model_create_multi
    def create(self, vals_list):
        result = self.browse()
        for vals in vals_list:
            order = self.env['step.packing.order'].browse(vals['order_id'])
            order.check_access('write')
            self.env.cr.execute('SELECT id FROM step_packing_order WHERE id=%s FOR UPDATE', [order.id])
            order.invalidate_recordset()
            if order.state == 'closed' or vals.get('state', 'draft') != 'draft' or vals.get('approved_by') or vals.get('approved_at'):
                raise UserError(_('Cree instructivos en borrador para una OP abierta.'))
            versions = self.search([('order_id', '=', order.id)]).mapped('version')
            vals['version'] = max(versions, default=0) + 1
            result |= super().create([vals])
        return result

    def action_approve(self):
        if not self.env.user.has_group('stock.group_stock_manager'):
            raise UserError(_('Un administrador de Inventario debe aprobar el instructivo.'))
        self.check_access('write')
        for record in self:
            self.env.cr.execute('SELECT id FROM step_packing_instruction WHERE id=%s FOR UPDATE', [record.id])
            record.invalidate_recordset()
            if record.state != 'draft' or not record.instruction or record.order_id.state == 'closed':
                raise ValidationError(_('El instructivo debe estar en borrador, con instrucciones y OP abierta.'))
            record.with_context(_instruction_approval=_APPROVAL).write({'state': 'approved', 'approved_by': self.env.uid, 'approved_at': fields.Datetime.now()})
        return True

    def write(self, vals):
        self.check_access('write')
        if self:
            self.env.cr.execute('SELECT id FROM step_packing_instruction WHERE id IN %s ORDER BY id FOR UPDATE', [tuple(sorted(self.ids))])
            self.invalidate_recordset()
        if self.env.context.get('_instruction_approval') is not _APPROVAL:
            if any(row.state != 'draft' for row in self) or {'state', 'approved_by', 'approved_at', 'version', 'order_id'} & vals.keys():
                raise UserError(_('Un instructivo aprobado conserva su versión. Cree una nueva para cambiarlo.'))
        return super().write(vals)

    def unlink(self):
        self.check_access('unlink')
        if self:
            self.env.cr.execute('SELECT id FROM step_packing_instruction WHERE id IN %s ORDER BY id FOR UPDATE', [tuple(sorted(self.ids))])
            self.invalidate_recordset()
        if any(row.state != 'draft' for row in self):
            raise UserError(_('No se elimina un instructivo aprobado.'))
        return super().unlink()


class PackingOrder(models.Model):
    _inherit = 'step.packing.order'
    instruction_ids = fields.One2many('step.packing.instruction', 'order_id', string='Versiones de instructivo')
