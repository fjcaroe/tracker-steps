"""Receive C tags from the picking, retaining native packages and stock moves."""
from odoo import fields, models, _
from odoo.exceptions import ValidationError
from odoo.tools.float_utils import float_compare


class Package(models.Model):
    _inherit = 'stock.quant.package'

    step_process_reception_id = fields.Many2one(
        'stock.picking', string='Recepción de origen', copy=False, readonly=True, index=True)


class Picking(models.Model):
    _inherit = 'stock.picking'

    def button_validate(self):
        # Also covers the native backorder wizard's second validation call.
        with self.env.cr.savepoint():
            for picking in self.filtered(lambda p: p.step_fruit_reception_kind == 'process'
                                         and p.state not in ('done', 'cancel')):
                picking._prepare_process_tags()
            return super().button_validate()

    def _prepare_process_tags(self):
        self.ensure_one()
        self.check_access('write')
        self.env.cr.execute('SELECT id FROM stock_picking WHERE id=%s FOR UPDATE', [self.id])
        self.invalidate_recordset()
        if self.state in ('done', 'cancel'):
            return
        producer = self.fruit_fundo_id.partner_id
        if not producer or not self.fruit_species_id or not self.fruit_tag_line_ids:
            raise ValidationError(_('Indique fundo, especie y distribución por tarjas en Fruta.'))
        moves = self.move_ids.filtered(lambda m: m.state not in ('done', 'cancel'))
        if not moves:
            raise ValidationError(_('Registre el producto y la cantidad recibida en Operaciones.'))
        names = [row.tag_number.strip() if row.tag_number else '' for row in self.fruit_tag_line_ids]
        if not all(names) or len(set(names)) != len(names):
            raise ValidationError(_('Indique un número distinto para cada tarja de la recepción.'))
        plans = []
        totals = {move.id: 0.0 for move in moves}
        kg = self.env.ref('uom.product_uom_kgm')
        for row, name in zip(self.fruit_tag_line_ids, names):
            if row.kilos <= 0 or row.quantity <= 0 or float_compare(row.quantity, round(row.quantity), precision_digits=6):
                raise ValidationError(_('Cada tarja requiere kilos positivos y una cantidad entera de envases mayor a cero.'))
            candidates = moves
            if row.product_id:
                candidates = candidates.filtered(lambda m: m.product_id == row.product_id)
            if row.packaging_id:
                candidates = candidates.filtered(lambda m: m.product_id == row.packaging_id.product_id
                                                 and m.product_packaging_id == row.packaging_id)
            if len(candidates) != 1:
                raise ValidationError(_('La tarja %s debe identificar un producto y embalaje de una única operación.') % name)
            move = candidates
            if move.product_id.tracking == 'serial':
                raise ValidationError(_('La recepción de fruta por tarjas requiere producto sin seguimiento o por lotes.'))
            if move.product_uom.category_id == kg.category_id:
                quantity = kg._compute_quantity(row.kilos, move.product_uom, round=False)
            elif row.packaging_id:
                quantity = move.product_id.uom_id._compute_quantity(
                    row.quantity * row.packaging_id.qty, move.product_uom, round=False)
            else:
                raise ValidationError(_('Indique el embalaje para convertir los envases a la unidad de stock.'))
            if quantity <= 0:
                raise ValidationError(_('La cantidad de stock de cada tarja debe ser positiva.'))
            totals[move.id] += quantity
            stock_lines = move.move_line_ids
            if any(line.package_id or line.owner_id and line.owner_id != producer for line in stock_lines):
                raise ValidationError(_('Revise los paquetes de origen o propietarios incompatibles en Operaciones.'))
            if any(line.location_id != move.location_id or line.location_dest_id != move.location_dest_id for line in stock_lines):
                raise ValidationError(_('Revise las ubicaciones detalladas: difieren de la operación de la recepción.'))
            lots = stock_lines.lot_id
            lot = row.stock_lot_id
            if not lot and len(lots) == 1:
                lot = lots
            if lot and lots and lot not in lots:
                raise ValidationError(_('El lote de la tarja no coincide con el lote ya capturado en Operaciones.'))
            if (len(lots) > 1 and not row.stock_lot_id) or any(line.lot_name for line in stock_lines):
                raise ValidationError(_('Seleccione el lote de stock de cada tarja antes de validar.'))
            if move.product_id.tracking != 'none' and not lot:
                raise ValidationError(_('Indique el lote de stock en la tarja %s.') % name)
            if lot and (lot.product_id != move.product_id or lot.company_id != self.company_id):
                raise ValidationError(_('El lote debe pertenecer al producto y empresa de la recepción.'))
            plans.append((row, name, move, quantity, lot))
        for move in moves:
            for lot in move.move_line_ids.lot_id:
                previous_qty = sum(line.product_uom_id._compute_quantity(line.quantity, move.product_uom, round=False)
                                   for line in move.move_line_ids.filtered(lambda line: line.lot_id == lot))
                distributed = sum(q for _, _, operation, q, assigned_lot in plans if operation == move and assigned_lot == lot)
                if float_compare(previous_qty, distributed, precision_rounding=move.product_uom.rounding):
                    raise ValidationError(_('La distribución por tarjas debe conservar los kilos o unidades de cada lote capturado.'))
            if float_compare(totals[move.id], move.quantity, precision_rounding=move.product_uom.rounding):
                raise ValidationError(_('La distribución de tarjas debe coincidir con la cantidad recibida en Operaciones: %s.') % move.product_id.display_name)
        for name in sorted(names):
            self.env.cr.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))', ['steps-process-tag:' + name])
        packages = self.env['stock.quant.package']
        for row, name, move, quantity, lot in plans:
            # Serialize even when the package has not been created yet.
            found = packages.sudo().search([('name', '=', name)]).with_env(self.env)
            if len(found) > 1 or row.package_id and row.package_id != found:
                raise ValidationError(_('El número %s no identifica una única tarja compatible.') % name)
            package = found
            if package:
                self.env.cr.execute('SELECT id FROM stock_quant_package WHERE id=%s FOR UPDATE', [package.id])
                package.invalidate_recordset()
                other_rows = self.env['step.packing.picking.tag.line'].sudo().search([
                    ('package_id', '=', package.id), ('picking_id', '!=', self.id)], limit=1)
                other_stock = self.env['stock.move.line'].sudo().search([
                    '|', ('package_id', '=', package.id), ('result_package_id', '=', package.id),
                    '|', ('picking_id', '!=', self.id), ('state', '=', 'done')], limit=1)
                if (not package.is_fruit_tag or package.step_tag_kind != 'C'
                        or package.step_tag_state not in ('created', 'validated')
                        or package.quant_ids or other_rows or other_stock
                        or package.company_id and package.company_id != self.company_id
                        or package.step_process_reception_id and package.step_process_reception_id != self
                        or package.step_producer_id and package.step_producer_id != producer
                        or package.step_export_shipment_ids or package.step_packing_production_id
                        or self.env['step.packing.production'].sudo().search_count([('step_packing_input_tag_ids','in',package.ids)])):
                    raise ValidationError(_('La tarja %s ya está utilizada o pertenece a otro origen.') % name)
            base_quantity = move.product_uom._compute_quantity(quantity, move.product_id.uom_id, round=False)
            metadata = {'fundo_id': self.fruit_fundo_id.id, 'especie_id': self.fruit_species_id.id,
                        'variedad_id': self.fruit_variety_id.id, 'step_export_season_id': self.fruit_season_id.id,
                        'fruit_type': self.step_fruit_type, 'fruit_category_id': self.fruit_category_id.id,
                        'fruit_class_id': self.step_fruit_origin_class_id.id,
                        'harvest_date': self.fruit_harvest_date, 'step_packaging_id': row.packaging_id.id,
                        'package_type_id': move.step_fruit_pallet_type_id.id}
            if row.caliber_id:
                caliber = self.env['step.management.fruit.caliber'].search([
                    ('step_contract_caliber_id', '=', row.caliber_id.id),
                    ('company_id', 'in', [False, self.company_id.id])])
                if len(caliber) != 1:
                    raise ValidationError(_('El calibre de la tarja requiere una equivalencia única en el maestro de calibres.'))
                metadata['fruit_caliber_id'] = caliber.id
            if row.brand:
                metadata['label'] = row.brand
            if package:
                for key, value in metadata.items():
                    old = package[key]
                    if old and (old.id if hasattr(old, 'id') else old) != value:
                        raise ValidationError(_('El origen de la tarja %s difiere de esta recepción.') % name)
            if package and package.step_tag_state == 'validated':
                detail = package.step_tag_line_ids
                # Recover only a prematurely validated, never-received tag already
                # linked to this receipt. Historical/used tags remain immutable.
                if (row.package_id != package or len(detail) != 1
                        or detail.product_id != move.product_id or detail.producer_id != producer
                        or float_compare(detail.kilos, row.kilos, precision_digits=2)
                        or not any(not float_compare(detail.quantity, q, precision_digits=6)
                                   for q in (base_quantity, row.quantity))):
                    raise ValidationError(_('La tarja validada %s no corresponde al detalle pendiente de esta recepción.') % name)
                for key, value in metadata.items():
                    old = package[key]
                    if old and (old.id if hasattr(old, 'id') else old) != value:
                        raise ValidationError(_('El origen de la tarja validada %s difiere de esta recepción.') % name)
                package.write({'step_tag_state': 'created'})
            values = dict(metadata, name=name, is_fruit_tag=True, step_tag_kind='C',
                          step_producer_id=producer.id, step_process_reception_id=self.id,
                          box_count=int(row.quantity))
            if package:
                package.write(values)
                package.step_tag_line_ids.unlink()
            else:
                package = packages.create(values)
            self.env['step.fruit.package.line'].create({
                'package_id': package.id, 'producer_id': producer.id, 'product_id': move.product_id.id,
                'quantity': base_quantity, 'kilos': row.kilos, 'boxes': row.quantity})
            row.write({'tag_number': name, 'package_id': package.id, 'product_id': move.product_id.id,
                       'box_count': row.quantity})
            packages |= package
        if any(line.result_package_id and line.result_package_id not in packages for line in moves.move_line_ids):
            raise ValidationError(_('Las operaciones contienen paquetes que no figuran en la distribución de tarjas.'))
        # Rebuild only this open receipt's detailed distribution; the demand and
        # native moves are preserved, including the standard backorder flow.
        moves.move_line_ids.unlink()
        if self.state == 'draft':
            moves._action_confirm(merge=False)
        moves._do_unreserve()
        for row, name, move, quantity, lot in plans:
            self.env['stock.move.line'].create({
                'move_id': move.id, 'picking_id': self.id, 'company_id': self.company_id.id,
                'product_id': move.product_id.id, 'product_uom_id': move.product_uom.id,
                'quantity': quantity, 'lot_id': lot.id, 'owner_id': producer.id,
                'location_id': move.location_id.id, 'location_dest_id': move.location_dest_id.id,
                'result_package_id': row.package_id.id})

    def _create_backorder(self, backorder_moves=None):
        backorders = super()._create_backorder(backorder_moves=backorder_moves)
        for picking in backorders.filtered(lambda p: p.step_fruit_reception_kind == 'process'):
            picking.fruit_tag_line_ids.unlink()
            picking.write({'step_fruit_gross_kg': 0, 'step_fruit_truck_tare_kg': 0,
                           'step_fruit_container_tare_kg': 0, 'step_fruit_transfer_tare_kg': 0})
        return backorders
