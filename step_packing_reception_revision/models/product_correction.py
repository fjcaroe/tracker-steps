"""Reclassify intact third-party fruit with native stock moves and keep the original receipt."""
from odoo import _, api, fields, models
from odoo.addons.step_inventory_packing.models.fruit_package import StepFruitPackageLine
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools.float_utils import float_compare


_CORRECTION = object()
_AUDIT_FIELDS = {'step_receipt_correction_line_id', 'step_receipt_correction_id',
                 'step_receipt_correction_direction', 'step_receipt_correction_reason'}


def _internal(records):
    return records.env.context.get('_receipt_product_correction') is _CORRECTION


class FruitPackageLine(models.Model):
    _inherit = 'step.fruit.package.line'

    def _step_write_corrected_product(self, product, lot):
        self.ensure_one()
        self.check_access('write')
        if (not _internal(self) or not self.env.user.has_group('stock.group_stock_manager')
                or self.package_id.step_tag_kind != 'C' or self.package_id.step_tag_state != 'validated'):
            raise AccessError(_('Use la corrección de producto de la recepción.'))
        profiles = getattr(self.env.user, '_step_application_levels', None)
        levels = profiles() if profiles else None
        if levels is not None and levels.get('packing', 0) < 2 and not self.env.su:
            raise AccessError(_('El perfil no permite modificar una tarja de Packing.'))
        self._check_open_ot()
        # The stock correction has already completed in this transaction.
        # Skip the ordinary immutability guard for these two fields only;
        # retain the ORM constraints, including the product of the lot.
        return super(StepFruitPackageLine, self).write({'product_id': product.id, 'lot_id': lot.id})


class ReceiptLine(models.Model):
    _inherit = 'step.packing.picking.tag.line'
    _rec_name = 'tag_number'

    def write(self, values):
        if not _internal(self) and {'product_id', 'stock_lot_id'}.intersection(values) and any(
                line.picking_id.state == 'done' and line.picking_id.step_fruit_reception_kind == 'process'
                and any(name in values and line[name].id != (values[name] or False)
                        for name in ('product_id', 'stock_lot_id')) for line in self):
            raise UserError(_('Use Corregir producto en la recepción para cambiar una tarja realizada.'))
        return super().write(values)


class Move(models.Model):
    _inherit = 'stock.move'

    step_receipt_correction_line_id = fields.Many2one(
        'step.packing.picking.tag.line', readonly=True, copy=False, ondelete='restrict')
    step_receipt_correction_id = fields.Many2one(related='step_receipt_correction_line_id.picking_id',
                                               store=True, index=True)
    step_receipt_correction_direction = fields.Selection(
        [('remove', 'Producto anterior'), ('add', 'Producto corregido')], readonly=True, copy=False)
    step_receipt_correction_reason = fields.Char('Motivo de la corrección', readonly=True, copy=False)

    @api.model_create_multi
    def create(self, values_list):
        if not _internal(self) and any(_AUDIT_FIELDS.intersection(values) for values in values_list):
            raise AccessError(_('Use la corrección de producto de la recepción.'))
        return super().create(values_list)

    def write(self, values):
        if not _internal(self) and _AUDIT_FIELDS.intersection(values):
            raise AccessError(_('La referencia de una corrección de producto se conserva.'))
        return super().write(values)


class Picking(models.Model):
    _inherit = 'stock.picking'

    step_product_correction_count = fields.Integer(compute='_compute_product_correction_count')

    def _compute_product_correction_count(self):
        counts = dict(self.env['stock.move']._read_group(
            [('step_receipt_correction_id', 'in', self.ids)], ['step_receipt_correction_id'], ['__count']))
        for picking in self:
            picking.step_product_correction_count = counts.get(picking, 0)

    def _step_check_product_correction(self):
        self.ensure_one()
        self.check_access('write')
        if not self.env.user.has_group('stock.group_stock_manager') or self.company_id not in self.env.companies:
            raise AccessError(_('La corrección requiere un responsable de Inventario de la compañía activa.'))
        if (self.state != 'done' or self.picking_type_code != 'incoming'
                or self.step_fruit_reception_kind != 'process'):
            raise UserError(_('Seleccione una recepción de fruta a proceso en estado Realizado.'))

    def action_step_correct_c_product(self):
        self._step_check_product_correction()
        return {
            'type': 'ir.actions.act_window', 'name': _('Corregir producto de tarjas C'),
            'res_model': 'step.reception.product.correction', 'view_mode': 'form', 'target': 'new',
            'context': {'default_picking_id': self.id},
        }

    def action_step_view_product_corrections(self):
        self.ensure_one()
        self.check_access('read')
        return {
            'type': 'ir.actions.act_window', 'name': _('Correcciones de producto'), 'res_model': 'stock.move',
            'view_mode': 'list,form', 'views': [
                (self.env.ref('step_packing_reception_revision.receipt_product_correction_moves').id, 'list'),
                (False, 'form'),
            ],
            'domain': [('step_receipt_correction_id', '=', self.id)], 'context': {'create': False},
        }


class CorrectProduct(models.TransientModel):
    _name = 'step.reception.product.correction'
    _description = 'Corregir producto de tarjas C realizadas'

    picking_id = fields.Many2one('stock.picking', required=True, readonly=True)
    company_id = fields.Many2one(related='picking_id.company_id')
    line_ids = fields.Many2many(
        'step.packing.picking.tag.line', 'step_receipt_product_correction_tag_rel',
        string='Tarjas C', required=True,
    )
    product_id = fields.Many2one('product.product', string='Producto corregido', required=True)
    reason = fields.Char('Motivo', required=True)

    def _lock_sources(self, tags):
        if 'step_advance_basis' in self.env['purchase.order']._fields:
            from odoo.addons.step_producer_advances.claims import lock_companies
            lock_companies(self.company_id)
        self.env.cr.execute('SELECT id FROM stock_picking WHERE id=%s FOR UPDATE', [self.picking_id.id])
        self.env.cr.execute('SELECT id FROM stock_quant_package WHERE id=ANY(%s) ORDER BY id FOR UPDATE', [tags.ids])
        self.env.cr.execute('SELECT id FROM stock_quant WHERE package_id=ANY(%s) ORDER BY id FOR UPDATE', [tags.ids])
        self.picking_id.invalidate_recordset()
        self.line_ids.invalidate_recordset()
        tags.invalidate_recordset()
        tags.quant_ids.invalidate_recordset()

    def _check_unused(self, tags):
        if (self.env['step.packing.production'].sudo().search_count([
                ('company_id', '=', self.company_id.id), ('step_packing_input_tag_ids', 'in', tags.ids),
        ], limit=1) or self.env['step.packing.repack.line'].sudo().search_count([
                ('repack_id.company_id', '=', self.company_id.id),
                '|', ('source_package_id', 'in', tags.ids), ('target_package_id', 'in', tags.ids),
        ], limit=1) or self.env['step.fruit.package.line'].sudo().search_count([
                ('source_package_id', 'in', tags.ids),
        ], limit=1)):
            raise UserError(_('Una de las tarjas ya está vinculada a un proceso o repaletizado.'))
        if any(tag.step_export_shipment_ids or tag.step_guide_ids or tag.step_invoice_ids for tag in tags):
            raise UserError(_('Una tarja vinculada a un documento de despacho o factura no se puede corregir aquí.'))
        purchases = self.env['purchase.order'].sudo()
        if 'step_fruit_tag_ids' in purchases._fields and purchases.search_count([
                ('company_id', '=', self.company_id.id), ('step_fruit_proforma', '=', True),
                ('step_fruit_state', '!=', 'cancel'), ('step_fruit_tag_ids', 'in', tags.ids),
        ], limit=1):
            raise UserError(_('Una tarja incluida en una proforma activa no se puede corregir aquí.'))

    def _plan_line(self, row):
        tag = row.package_id
        detail = tag.step_tag_line_ids
        quants = tag.quant_ids.filtered(lambda quant: quant.quantity or quant.reserved_quantity)
        if (tag.step_process_reception_id != self.picking_id or tag.company_id != self.company_id
                or tag.step_tag_kind != 'C' or tag.step_tag_state != 'validated'
                or len(detail) != 1 or len(quants) != 1):
            raise UserError(_('La tarja %s debe conservar su recepción, su detalle original y su stock íntegro.') % tag.name)
        quant = quants
        old = row.product_id
        weight = self.env.ref('uom.product_uom_kgm').category_id
        if (not old or old == self.product_id or detail.product_id != old or quant.product_id != old
                or old.uom_id != self.product_id.uom_id or old.uom_id.category_id != weight
                or old.tracking != self.product_id.tracking or old.tracking == 'serial'):
            raise ValidationError(_('Elija otro producto almacenable con la misma unidad de peso y seguimiento.'))
        if (quant.company_id != self.company_id or quant.location_id != self.picking_id.location_dest_id
                or quant.location_id.usage != 'internal' or quant.reserved_quantity or quant.quantity <= 0
                or quant.owner_id != detail.producer_id or quant.owner_id == self.company_id.partner_id
                or quant.lot_id != detail.lot_id or quant.lot_id != row.stock_lot_id
                or (old.tracking == 'lot' and not quant.lot_id)
                or float_compare(quant.quantity, detail.quantity, precision_rounding=old.uom_id.rounding)
                or float_compare(detail.kilos, row.kilos, precision_digits=2)):
            raise UserError(_('La tarja %s debe conservar existencias de tercero completas, sin reservas y en la recepción original.') % tag.name)
        history = self.env['stock.move.line'].sudo().search([
            ('state', '!=', 'cancel'), '|', ('package_id', '=', tag.id), ('result_package_id', '=', tag.id),
        ])
        original = history.filtered(lambda line: line.picking_id == self.picking_id
                                    and line.result_package_id == tag and line.state == 'done')
        if not original or any(line.move_id.step_receipt_correction_line_id != row for line in history - original):
            raise UserError(_('La tarja %s tiene movimientos posteriores ajenos a la corrección de producto.') % tag.name)
        return detail, quant

    def _replacement_lot(self, lot):
        if not lot:
            return lot
        self.env.cr.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',
                            [f'steps-reception-lot:{self.company_id.id}:{self.product_id.id}:{lot.name}'])
        lots = self.env['stock.lot'].with_company(self.company_id)
        found = lots.search([('product_id', '=', self.product_id.id), ('name', '=', lot.name),
                             ('company_id', 'in', [False, self.company_id.id])])
        if len(found) > 1 or found and found.company_id != self.company_id:
            raise UserError(_('El nombre de lote %s no identifica un lote único de la compañía.') % lot.name)
        return found or lots.create({'product_id': self.product_id.id, 'name': lot.name, 'company_id': self.company_id.id})

    def _reclassify_line(self, row, detail, quant):
        tag = row.package_id
        old, target = detail.product_id, self.product_id
        owner, location, old_lot, quantity = quant.owner_id, quant.location_id, quant.lot_id, quant.quantity
        new_lot = self._replacement_lot(old_lot)
        loss = old.with_company(self.company_id).property_stock_inventory
        gain = target.with_company(self.company_id).property_stock_inventory
        for place in loss | gain:
            if place.usage != 'inventory' or place.scrap_location or place.company_id != self.company_id:
                raise UserError(_('Configure las ubicaciones de ajuste de inventario en la compañía receptora.'))
        if not loss or not gain:
            raise UserError(_('Configure las ubicaciones de ajuste de inventario de ambos productos.'))
        moves = self.env['stock.move'].with_company(self.company_id)
        Move = moves.with_context(_receipt_product_correction=_CORRECTION)
        for direction, product, lot, src, dst, source_tag, result_tag in (
                ('remove', old, old_lot, location, loss, tag.id, False),
                ('add', target, new_lot, gain, location, False, tag.id)):
            move = Move.create({
                'name': _('Corrección de producto de tarja %s') % tag.name, 'origin': self.picking_id.name,
                'company_id': self.company_id.id, 'product_id': product.id, 'product_uom': product.uom_id.id,
                'product_uom_qty': quantity, 'location_id': src.id, 'location_dest_id': dst.id,
                'step_receipt_correction_line_id': row.id, 'step_receipt_correction_direction': direction,
                'step_receipt_correction_reason': self.reason.strip(),
            })
            move._action_confirm(merge=False)
            move._do_unreserve()
            self.env['stock.move.line'].with_company(self.company_id).create({
                'move_id': move.id, 'company_id': self.company_id.id, 'product_id': product.id,
                'product_uom_id': product.uom_id.id, 'quantity': quantity, 'lot_id': lot.id,
                'location_id': src.id, 'location_dest_id': dst.id, 'owner_id': owner.id,
                'package_id': source_tag, 'result_package_id': result_tag, 'picked': True,
            })
            move.picked = True
            moves |= move
        moves._action_done(cancel_backorder=True)
        if set(moves.mapped('state')) != {'done'} or moves.stock_valuation_layer_ids:
            raise ValidationError(_('La corrección de stock de tercero no debe generar valoración.'))
        stock = tag.quant_ids.filtered(lambda item: item.quantity or item.reserved_quantity)
        if (len(stock) != 1 or stock.product_id != target or stock.owner_id != owner
                or stock.lot_id != new_lot or stock.location_id != location or stock.reserved_quantity
                or float_compare(stock.quantity, quantity, precision_rounding=target.uom_id.rounding)):
            raise ValidationError(_('La corrección no conservó íntegramente el stock de la tarja.'))
        detail.with_context(_receipt_product_correction=_CORRECTION)._step_write_corrected_product(target, new_lot)
        row.with_context(_receipt_product_correction=_CORRECTION).write({'product_id': target.id, 'stock_lot_id': new_lot.id})
        tag._check_step_tag()
        return moves

    def action_apply(self):
        self.ensure_one()
        self.check_access('write')
        self.picking_id._step_check_product_correction()
        self.line_ids.check_access('write')
        product = self.product_id
        product.check_access('read')
        if (not self.line_ids or self.line_ids.picking_id != self.picking_id
                or not product.active or not product.is_storable
                or product.company_id and product.company_id not in self.company_id.parent_ids
                or not (self.reason or '').strip()):
            raise ValidationError(_('Seleccione las tarjas de esta recepción, un producto almacenable y el motivo.'))
        tags = self.line_ids.package_id
        if len(tags) != len(self.line_ids):
            raise ValidationError(_('Cada línea debe identificar una tarja distinta.'))
        tags.check_access('write')
        with self.env.cr.savepoint():
            self._lock_sources(tags)
            self.picking_id._step_check_product_correction()
            if self.line_ids.package_id != tags or self.line_ids.picking_id != self.picking_id:
                raise UserError(_('La recepción cambió mientras preparaba la corrección. Vuelva a abrirla.'))
            self._check_unused(tags)
            plans = [(row, *self._plan_line(row)) for row in self.line_ids]
            for row, detail, quant in plans:
                self._reclassify_line(row, detail, quant)
        return {'type': 'ir.actions.act_window_close'}
