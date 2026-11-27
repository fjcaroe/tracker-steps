"""Correct the received producer using auditable native ownership movements."""
from collections import defaultdict

from odoo import Command, _, api, fields, models
from odoo.addons.step_inventory_packing.models.fruit_package import (
    StockQuantPackage as ImmutablePackage, StepFruitPackageLine as ImmutableDetail,
)
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools.float_utils import float_compare
from odoo.tools.misc import clean_context


_CHANGE = object()
_AUDIT = {'step_producer_receipt_id', 'step_producer_tag_id',
          'step_producer_change_direction', 'step_producer_change_reason'}


class Move(models.Model):
    _inherit = 'stock.move'

    step_producer_receipt_id = fields.Many2one('stock.picking', readonly=True, copy=False, ondelete='restrict', index=True)
    step_producer_tag_id = fields.Many2one('stock.quant.package', readonly=True, copy=False, ondelete='restrict')
    step_producer_change_direction = fields.Selection(
        [('remove', 'Productor anterior'), ('add', 'Productor corregido')], readonly=True, copy=False)
    step_producer_change_reason = fields.Char('Motivo del cambio de productor', readonly=True, copy=False)

    @api.model_create_multi
    def create(self, values_list):
        if self.env.context.get('_step_receipt_producer') is not _CHANGE and (
                any(_AUDIT.intersection(values) for values in values_list)
                or any(self.env.context.get('default_' + name) for name in _AUDIT)):
            raise AccessError(_('Use Cambiar productor en la recepción.'))
        return super().create(values_list)

    def write(self, values):
        if _AUDIT.intersection(values) and self.env.context.get('_step_receipt_producer') is not _CHANGE:
            raise AccessError(_('El historial de cambio de productor se conserva.'))
        return super().write(values)


class Package(models.Model):
    _inherit = 'stock.quant.package'

    def _step_received_producer_receipt(self):
        self.ensure_one()
        receipt = self.step_process_reception_id
        if not receipt:
            # Older receipts already have the native tag row, but predate the
            # package's explicit origin link. Resolve that existing relation.
            receipt = self.env['step.packing.picking.tag.line'].search([
                ('package_id', '=', self.id), ('picking_id.state', '=', 'done'),
                ('picking_id.step_fruit_reception_kind', '=', 'process'),
                ('picking_id.step_fruit_reversal_id', '=', False)]).picking_id
        if len(receipt) != 1:
            raise UserError(_('La tarja debe identificar una única recepción de fruta a proceso.'))
        return receipt

    def action_step_change_received_producer(self):
        self.ensure_one()
        self.check_access('write')
        if self.step_tag_kind != 'C':
            raise UserError(_('Seleccione una tarja C con recepción de origen.'))
        return self._step_received_producer_receipt().action_step_change_received_producer()

    def _step_set_received_producer(self, producer):
        self.check_access('write')
        if self.env.context.get('_step_receipt_producer') is not _CHANGE:
            raise AccessError(_('Use Cambiar productor en la recepción.'))
        # Only this field bypasses the validated-tag edit guard. Preserve the
        # original farm, all quantities and all ordinary ORM constraints.
        for tag in self:
            detail = tag.step_tag_line_ids.with_context(_step_receipt_producer=_CHANGE)
            detail.check_access('write')
            super(ImmutableDetail, detail).write({'producer_id': producer.id})
        super(ImmutablePackage, self).write({'step_producer_id': producer.id})
        self._check_step_tag()


class Picking(models.Model):
    _inherit = 'stock.picking'

    step_producer_change_move_ids = fields.One2many('stock.move', 'step_producer_receipt_id', readonly=True)
    step_producer_change_count = fields.Integer(compute='_compute_producer_change_count')

    def _compute_producer_change_count(self):
        for picking in self:
            picking.step_producer_change_count = len(picking.step_producer_change_move_ids)

    def _step_check_received_producer_access(self):
        self.ensure_one()
        self.check_access('write')
        levels = getattr(self.env.user, '_step_application_levels', lambda: None)()
        if (not self.env.user.has_group('stock.group_stock_manager')
                or self.company_id not in self.env.companies
                or levels is not None and levels.get('packing', 0) < 2 and not self.env.su):
            raise AccessError(_('El cambio requiere permiso de modificación de Packing y responsable de Inventario en la empresa activa.'))
        if (self.state != 'done' or self.picking_type_code != 'incoming'
                or self.step_fruit_reception_kind != 'process' or self.step_fruit_reversal_id):
            raise UserError(_('Seleccione una recepción vigente de fruta a proceso realizada.'))

    def action_step_change_received_producer(self):
        self._step_check_received_producer_access()
        return {'type': 'ir.actions.act_window', 'name': _('Cambiar productor recibido'),
                'res_model': 'step.receipt.producer.change', 'view_mode': 'form', 'target': 'new',
                'context': {'default_picking_id': self.id, 'default_previous_producer_id': self.partner_id.id}}

    def action_step_view_producer_changes(self):
        self.ensure_one()
        self.check_access('read')
        return {'type': 'ir.actions.act_window', 'name': _('Cambios de productor'),
                'res_model': 'stock.move', 'view_mode': 'list,form',
                'views': [(self.env.ref('step_packing_producer_change.receipt_producer_moves').id, 'list'), (False, 'form')],
                'domain': [('step_producer_receipt_id', '=', self.id)], 'context': {'create': False}}

    def write(self, values):
        if 'partner_id' in values and self.env.context.get('_step_receipt_producer') is not _CHANGE and any(
                p.state == 'done' and p.step_fruit_reception_kind == 'process'
                and p.partner_id.id != (values['partner_id'] or False) for p in self):
            raise UserError(_('Use Cambiar productor para actualizar también las tarjas C y su stock.'))
        return super().write(values)


class ProducerChange(models.TransientModel):
    _name = 'step.receipt.producer.change'
    _description = 'Cambiar productor recibido en inventario'

    picking_id = fields.Many2one('stock.picking', required=True, readonly=True)
    company_id = fields.Many2one(related='picking_id.company_id')
    previous_producer_id = fields.Many2one('res.partner', string='Recibido de', required=True, readonly=True)
    producer_id = fields.Many2one('res.partner', string='Nuevo productor', required=True,
                                 domain="[('is_productor', '=', True)]")
    tag_ids = fields.Many2many('stock.quant.package', compute='_compute_tags', string='Tarjas C afectadas')
    reason = fields.Char('Motivo', required=True)

    @api.depends('picking_id')
    def _compute_tags(self):
        for wizard in self:
            wizard.tag_ids = wizard.picking_id.fruit_tag_line_ids.package_id

    def _plan(self, tags):
        plans = {}
        for tag in tags:
            detail = tag.step_tag_line_ids
            quants = tag.quant_ids.filtered(lambda q: q.quantity or q.reserved_quantity)
            if (not tag.is_fruit_tag or tag.step_tag_kind != 'C' or tag.step_tag_state != 'validated'
                    or tag._step_received_producer_receipt() != self.picking_id or tag.company_id != self.company_id
                    or not detail or not quants or any(q.quantity <= 0 or q.location_id.usage != 'internal'
                        or q.company_id != self.company_id or q.owner_id != self.previous_producer_id for q in quants)
                    or any(line.producer_id != self.previous_producer_id for line in detail)
                    or tag.step_producer_id != self.previous_producer_id):
                raise UserError(_('La tarja %s debe permanecer íntegra en inventario, sin despacho ni proceso.') % tag.name)
            totals = defaultdict(float)
            expected = defaultdict(float)
            for quant in quants:
                totals[(quant.product_id, quant.lot_id)] += quant.quantity
            for line in detail:
                expected[(line.product_id, line.lot_id)] += line.quantity
            if totals.keys() != expected.keys() or any(float_compare(total, expected[key],
                    precision_rounding=key[0].uom_id.rounding) for key, total in totals.items()):
                raise UserError(_('La tarja %s ya no conserva todo el stock recibido.') % tag.name)
            history = self.env['stock.move.line'].sudo().search([
                ('state', '=', 'done'), ('package_id', '=', tag.id), ('quantity', '>', 0)])
            if any(line.location_dest_id.usage != 'internal' and not line.move_id.step_producer_receipt_id
                   and not line.move_id.step_receipt_correction_id for line in history):
                raise UserError(_('La tarja %s registra fruta despachada o procesada.') % tag.name)
            for quant in quants:
                key = (tag, quant.product_id, quant.lot_id, quant.location_id)
                if key not in plans:
                    plans[key] = [0.0, quant.in_date]
                plans[key][0] += quant.quantity
                plans[key][1] = min(plans[key][1], quant.in_date)
        return [(*key, quantity, in_date) for key, (quantity, in_date) in plans.items()]

    def action_apply(self):
        self.ensure_one()
        self.check_access('write')
        receipt, producer = self.picking_id, self.producer_id
        receipt._step_check_received_producer_access()
        producer.check_access('read')
        if not producer.active or not producer.is_productor or producer == self.previous_producer_id or not (self.reason or '').strip():
            raise ValidationError(_('Seleccione otro productor activo e indique el motivo.'))
        with self.env.cr.savepoint():
            if 'step_advance_basis' in self.env['purchase.order']._fields:
                from odoo.addons.step_producer_advances.claims import lock_companies
                lock_companies(self.company_id)
            self.env.cr.execute('SELECT id FROM stock_picking WHERE id=%s FOR UPDATE', [receipt.id])
            receipt.invalidate_recordset()
            receipt._step_check_received_producer_access()
            tags = receipt.fruit_tag_line_ids.package_id
            if not tags or len(tags) != len(receipt.fruit_tag_line_ids) or receipt.partner_id != self.previous_producer_id:
                raise UserError(_('La recepción cambió. Abra nuevamente Cambiar productor.'))
            tags.check_access('write')
            self.env.cr.execute('SELECT id FROM stock_quant_package WHERE id=ANY(%s) ORDER BY id FOR UPDATE', [tags.ids])
            pending = self.env['stock.move.line'].search([
                ('state', 'not in', ['done', 'cancel']), ('package_id', 'in', tags.ids)])
            if pending:
                pending.check_access('write')
                self.env.cr.execute('SELECT id FROM stock_move_line WHERE id=ANY(%s) ORDER BY id FOR UPDATE', [pending.ids])
                pending.invalidate_recordset()
            self.env.cr.execute('SELECT id FROM stock_quant WHERE package_id=ANY(%s) ORDER BY id FOR UPDATE', [tags.ids])
            tags.invalidate_recordset()
            tags.quant_ids.invalidate_recordset()
            plans = self._plan(tags)
            # Check native contact/company rules before doing any stock work.
            receipt.with_context(_step_receipt_producer=_CHANGE, tracking_disable=True).write({'partner_id': producer.id})
            saved = [(line, line.quantity, line.picked) for line in pending]
            pending.write({'quantity': 0})
            Move = self.env['stock.move'].with_context(
                clean_context(self.env.context), _step_receipt_producer=_CHANGE).with_company(self.company_id)
            changes = self.env['stock.move']
            for tag, product, lot, location, quantity, in_date in plans:
                adjustment = product.with_company(self.company_id).property_stock_inventory
                if not adjustment or adjustment.usage != 'inventory' or adjustment.scrap_location or adjustment.company_id and adjustment.company_id != self.company_id:
                    raise UserError(_('Configure la ubicación nativa de ajuste de inventario de la compañía.'))
                for direction, owner, src, dst, source_tag, result_tag in (
                        ('remove', self.previous_producer_id, location, adjustment, tag.id, False),
                        ('add', producer, adjustment, location, False, tag.id)):
                    move = Move.create({
                        'name': _('Cambio de productor %s') % tag.name, 'origin': receipt.name,
                        'company_id': self.company_id.id, 'product_id': product.id, 'product_uom': product.uom_id.id,
                        'picking_id': False,
                        'product_uom_qty': quantity, 'location_id': src.id, 'location_dest_id': dst.id,
                        'state': 'confirmed', 'is_inventory': True, 'picked': True, 'restrict_partner_id': owner.id,
                        'step_producer_receipt_id': receipt.id, 'step_producer_tag_id': tag.id,
                        'step_producer_change_direction': direction, 'step_producer_change_reason': self.reason.strip(),
                        'move_line_ids': [Command.create({
                            'product_id': product.id, 'product_uom_id': product.uom_id.id, 'quantity': quantity,
                            'location_id': src.id, 'location_dest_id': dst.id, 'owner_id': owner.id, 'lot_id': lot.id,
                            'package_id': source_tag, 'result_package_id': result_tag, 'picked': True})]})
                    move._action_done(cancel_backorder=True)
                    changes |= move
                # Preserve FIFO receipt age; this is the same physical fruit.
                quants = tag.quant_ids.filtered(lambda q: q.product_id == product and q.lot_id == lot
                    and q.location_id == location and q.owner_id == producer and q.quantity > 0)
                quants.write({'in_date': in_date})
            tags.with_context(_step_receipt_producer=_CHANGE)._step_set_received_producer(producer)
            for line, quantity, picked in saved:
                line.write({'owner_id': producer.id, 'quantity': quantity, 'picked': picked})
            for move in pending.move_id.filtered(lambda m: m.restrict_partner_id == self.previous_producer_id):
                lines = move.move_line_ids.filtered(lambda line: line.quantity > 0 and line.state != 'cancel')
                move.restrict_partner_id = producer if lines and all(line.owner_id == producer for line in lines) else False
            for picking in pending.picking_id.filtered(lambda p: p.owner_id == self.previous_producer_id):
                lines = picking.move_line_ids.filtered(lambda line: line.quantity > 0 and line.state != 'cancel')
                # A native picking's Assign Owner overrides every detail when
                # completed. Preserve mixed owners through the individual lines.
                picking.owner_id = producer if lines and all(line.owner_id == producer for line in lines) else False
            if set(changes.mapped('state')) != {'done'} or changes.picking_id:
                raise ValidationError(_('El cambio debe completar sus movimientos sin modificar las operaciones originales de recepción.'))
            for tag in tags:
                if tag.owner_id != producer or tag.step_producer_id != producer or tag.step_tag_line_ids.producer_id != producer:
                    raise ValidationError(_('No se conservó el productor y propietario de todas las tarjas.'))
        return {'type': 'ir.actions.act_window_close'}
