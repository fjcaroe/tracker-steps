"""The OT owns the lot label of its E/N output; stock.lot remains product/company scoped."""
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


def output_order(tag):
    if not tag.is_fruit_tag or tag.step_tag_kind not in ('E', 'N'):
        return tag.env['step.packing.production']
    orders = tag.step_packing_production_id or tag.env['step.packing.production'].search([
        ('step_packing_output_tag_ids', 'in', tag.ids)], limit=2)
    if len(orders) > 1:
        raise ValidationError(_('Una tarja resultante debe identificar una única OT.'))
    return orders


class PackingProduction(models.Model):
    _inherit = 'step.packing.production'

    step_output_lot_name = fields.Char(
        string='LOTE', copy=False,
        help='Lote común de las tarjas E y N. Por defecto se usa el número de esta OT.',
    )

    @api.model_create_multi
    def create(self, vals_list):
        with self.env.cr.savepoint():
            records = super().create(vals_list)
            for record in records:
                record.write({'step_output_lot_name': record.step_output_lot_name or record.name})
            return records

    def write(self, vals):
        if 'step_output_lot_name' in vals:
            self._lock_process()
            if any(order.state not in ('created', 'validated') for order in self):
                raise UserError(_('El lote se conserva después del cierre de la OT.'))
            with self.env.cr.savepoint():
                for order in self:
                    values = dict(vals, step_output_lot_name=(vals['step_output_lot_name'] or '').strip() or order.name)
                    super(PackingProduction, order).write(values)
                    order._sync_output_lots()
            return True
        with self.env.cr.savepoint():
            result = super().write(vals)
            if {'step_packing_output_tag_ids', 'company_id'} & vals.keys():
                self._sync_output_lots()
            return result

    def _lot_for_output_product(self, product):
        self.ensure_one()
        name = (self.step_output_lot_name or self.name).strip()
        self.env.cr.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',
                            [f'steps-reception-lot:{self.company_id.id}:{product.id}:{name}'])
        lots = self.env['stock.lot'].search([
            ('name', '=', name), ('product_id', '=', product.id), ('company_id', '=', self.company_id.id)])
        if len(lots) > 1:
            raise ValidationError(_('El lote debe identificar un único registro del producto y empresa.'))
        return lots or self.env['stock.lot'].create({
            'name': name, 'product_id': product.id, 'company_id': self.company_id.id})

    def _sync_output_lots(self):
        self._lock_process()
        for order in self:
            if order.state not in ('created', 'validated'):
                raise UserError(_('Los lotes se asignan antes de cerrar la OT.'))
            if not order.step_output_lot_name:
                models.Model.write(order, {'step_output_lot_name': order.name})
            tags = order.step_packing_output_tag_ids
            if any(tag.step_tag_kind not in ('E', 'N') or
                   tag.step_packing_production_id and tag.step_packing_production_id != order for tag in tags):
                raise ValidationError(_('Asigne el lote únicamente a las tarjas E y N de esta OT.'))
            if self.sudo().search_count([
                    ('id', '!=', order.id), ('step_packing_output_tag_ids', 'in', tags.ids)], limit=1):
                raise ValidationError(_('Una tarja resultante no puede compartir el lote de dos OT.'))
            if any(quant.quantity or quant.reserved_quantity for quant in tags.sudo().quant_ids):
                raise UserError(_('Una tarja con existencias conserva su lote de inventario.'))
            if self.env['stock.move.line'].sudo().search_count([
                    ('state', '!=', 'cancel'),
                    ('picking_id', 'not in', (order.step_close_reversal_ids |
                                             order.step_close_reversal_ids.return_id).ids),
                    '|', ('package_id', 'in', tags.ids), ('result_package_id', 'in', tags.ids)], limit=1):
                raise UserError(_('Una tarja con movimientos conserva su lote de inventario.'))
            for line in tags.step_tag_line_ids:
                lot = order._lot_for_output_product(line.product_id)
                if line.lot_id != lot:
                    # Only the lot relation may change on a prevalidated, never-stocked
                    # output. Native ACLs and constraints still run through Model.write.
                    models.Model.write(line, {'lot_id': lot.id})

    def _check_packing_tags(self):
        result = super()._check_packing_tags()
        self._sync_output_lots()
        return result


class PackageLine(models.Model):
    _inherit = 'step.fruit.package.line'

    @api.model_create_multi
    def create(self, vals_list):
        with self.env.cr.savepoint():
            values = []
            for supplied in vals_list:
                vals = dict(supplied)
                tag = self.env['stock.quant.package'].browse(vals.get('package_id'))
                order = output_order(tag)
                if order and vals.get('product_id'):
                    order._lock_process()
                    vals['lot_id'] = order._lot_for_output_product(self.env['product.product'].browse(vals['product_id'])).id
                values.append(vals)
            return super().create(values)

    def write(self, vals):
        if {'product_id', 'lot_id'} & vals.keys():
            with self.env.cr.savepoint():
                for line in self:
                    values = dict(vals)
                    order = output_order(line.package_id)
                    if order:
                        order._lock_process()
                        product = self.env['product.product'].browse(vals['product_id']) if 'product_id' in vals else line.product_id
                        values['lot_id'] = order._lot_for_output_product(product).id
                    super(PackageLine, line).write(values)
            return True
        return super().write(vals)
