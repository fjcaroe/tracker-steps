"""Operational controls: review materials per pallet before moving real stock."""
from collections import defaultdict
import hashlib
import json
from markupsafe import escape

from odoo import Command, api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools.float_utils import float_compare

_INTERNAL = object()
_REVERSAL = object()


class PackingProduction(models.Model):
    _inherit = 'step.packing.production'

    date = fields.Date('Fecha de proceso', default=fields.Date.context_today, required=True)
    process_type_id = fields.Many2one('step.packing.process.type', string='Tipo de proceso')
    packing_partner_id = fields.Many2one('res.partner', string='Planta')
    customer_id = fields.Many2one('res.partner', string='Cliente')
    shift = fields.Char('Turno')
    workers = fields.Integer('Dotación')
    started_at = fields.Datetime('Inicio')
    finished_at = fields.Datetime('Término')
    standard_kg_hour = fields.Float('Rendimiento estándar kg/h')
    fruit_type = fields.Selection([('conventional', 'Convencional'), ('organic', 'Orgánica')], compute='_compute_fruit_metrics')
    average_harvest_box_kg = fields.Float('Peso promedio caja cosecha', compute='_compute_fruit_metrics')
    harvest_age_days = fields.Integer('Días desde cosecha', compute='_compute_fruit_metrics')
    storage_days = fields.Integer('Días de permanencia', compute='_compute_fruit_metrics')
    caliber_2j_percent = fields.Float('% kilos 2J+', compute='_compute_fruit_metrics')
    caliber_breakdown = fields.Html('Kilos por resultado y calibre', compute='_compute_fruit_metrics')
    downtime_ids = fields.One2many('step.packing.downtime', 'production_id', string='Detenciones')
    total_hours = fields.Float('Horas totales', compute='_compute_performance')
    effective_hours = fields.Float('Horas efectivas', compute='_compute_performance')
    idle_percent = fields.Float('% tiempo ocioso', compute='_compute_performance')
    kg_hour = fields.Float('Kg por hora efectiva', compute='_compute_performance')
    kg_worker = fields.Float('Kg por trabajador', compute='_compute_performance')
    kg_worker_hour = fields.Float('Kg por hora-hombre efectiva', compute='_compute_performance')
    material_line_ids = fields.One2many('step.packing.material.consumption', 'production_id', string='Materiales por tarja')
    material_review_state = fields.Selection([
        ('pending', 'Pendiente de preparación'), ('review', 'En revisión'), ('approved', 'Aprobada'),
    ], default='pending', required=True, copy=False, string='Revisión de materiales')
    material_approved_by = fields.Many2one('res.users', readonly=True, copy=False)
    material_approved_at = fields.Datetime(readonly=True, copy=False)
    material_signature = fields.Char(copy=False, readonly=True)
    return_picking_id = fields.Many2one('stock.picking', string='Devolución al productor', readonly=True, copy=False)

    @api.depends('date', 'step_packing_input_tag_ids.fruit_type', 'step_packing_input_tag_ids.harvest_date',
                 'step_packing_input_tag_ids.received_at', 'step_packing_input_tag_ids.step_tag_line_ids.boxes',
                 'step_packing_input_kg', 'step_packing_output_tag_ids.fruit_caliber_id.step_2j_plus',
                 'step_packing_output_tag_ids.step_tag_line_ids.kilos', 'step_packing_export_kg')
    def _compute_fruit_metrics(self):
        for record in self:
            inputs = record.step_packing_input_tag_ids
            record.fruit_type = inputs[:1].fruit_type
            boxes = sum(inputs.mapped('step_tag_line_ids.boxes'))
            record.average_harvest_box_kg = record.step_packing_input_kg / boxes if boxes else 0
            harvested = inputs.filtered('harvest_date').mapped('harvest_date')
            received = inputs.filtered('received_at').mapped('received_at')
            record.harvest_age_days = max(0, (record.date - min(harvested)).days) if record.date and harvested else 0
            record.storage_days = max(0, (record.date - min(received).date()).days) if record.date and received else 0
            large = record.step_packing_output_tag_ids.filtered(lambda tag: tag.step_packing_result == 'export' and tag.fruit_caliber_id.step_2j_plus)
            record.caliber_2j_percent = sum(large.mapped('step_actual_kg')) / record.step_packing_export_kg * 100 if record.step_packing_export_kg else 0
            groups = defaultdict(float)
            labels = {'export': _('Exportación'), 'commercial': _('Comercial'), 'precaliber': _('Precalibre'), 'waste': _('Desecho')}
            for tag in record.step_packing_output_tag_ids:
                groups[labels.get(tag.step_packing_result, _('Sin clasificar')), tag.fruit_caliber_id.display_name or _('Sin calibre')] += tag.step_actual_kg
            rows = ['<tr><td>%s</td><td>%s</td><td>%.3f</td></tr>' % (escape(result), escape(caliber), kilos)
                    for (result, caliber), kilos in sorted(groups.items())]
            record.caliber_breakdown = '<table class="table table-sm"><thead><tr><th>Resultado</th><th>Calibre</th><th>Kilos</th></tr></thead><tbody>%s</tbody></table>' % ''.join(rows)

    def _check_packing_tags(self):
        result = super()._check_packing_tags()
        for record in self:
            if len(set((record.step_packing_input_tag_ids | record.step_packing_output_tag_ids).mapped('fruit_type'))) > 1:
                raise ValidationError(_('No mezcle fruta orgánica y convencional en una OT.'))
            for quant in record.step_packing_input_tag_ids.quant_ids.filtered(lambda row: row.quantity > 0):
                if quant.company_id != record.company_id or quant.owner_id and quant.owner_id != record.step_packing_input_tag_ids[0].step_tag_line_ids[0].producer_id:
                    raise ValidationError(_('El stock de materia prima debe pertenecer a esta empresa y al productor declarado.'))
        return result

    def _material_signature(self):
        self.ensure_one()
        values = []
        for tag in self.step_packing_output_tag_ids.sorted('id'):
            values.append((tag.id, tag.step_packing_result, [
                (line.product_id.id, line.quantity, line.boxes) for line in tag.step_tag_line_ids.sorted('id')]))
        return hashlib.sha256(json.dumps(values, sort_keys=True).encode()).hexdigest()

    @api.depends('started_at', 'finished_at', 'workers', 'downtime_ids.started_at',
                 'downtime_ids.finished_at', 'step_packing_input_kg')
    def _compute_performance(self):
        for record in self:
            total = ((record.finished_at - record.started_at).total_seconds() / 3600
                     if record.started_at and record.finished_at else 0)
            idle = sum(record.downtime_ids.mapped('hours'))
            effective = max(0, total - idle)
            record.total_hours = total
            record.effective_hours = effective
            record.idle_percent = idle / total * 100 if total > 0 else 0
            record.kg_hour = record.step_packing_input_kg / effective if effective > 0 else 0
            record.kg_worker = record.step_packing_input_kg / record.workers if record.workers > 0 else 0
            record.kg_worker_hour = record.kg_hour / record.workers if record.workers > 0 else 0

    @api.constrains('started_at', 'finished_at', 'workers', 'standard_kg_hour', 'downtime_ids')
    def _check_times(self):
        for record in self:
            if record.workers < 0 or record.standard_kg_hour < 0:
                raise ValidationError(_('Dotación y rendimiento no pueden ser negativos.'))
            if record.started_at and record.finished_at and record.finished_at <= record.started_at:
                raise ValidationError(_('El término debe ser posterior al inicio.'))
            previous_end = None
            for stop in record.downtime_ids.sorted('started_at'):
                if (previous_end and stop.started_at < previous_end or
                    record.started_at and stop.started_at < record.started_at or
                    record.finished_at and stop.finished_at > record.finished_at):
                    raise ValidationError(_('Las detenciones deben estar dentro del proceso y no superponerse.'))
                previous_end = stop.finished_at

    def _lock_process(self):
        if not self:
            return
        self.check_access('write')
        self.env.cr.execute('SELECT id FROM step_packing_production WHERE id IN %s ORDER BY id FOR UPDATE',
                            [tuple(self.ids)])
        self.invalidate_recordset()
        tags = self.step_packing_input_tag_ids | self.step_packing_output_tag_ids
        if tags:
            self.env.cr.execute('SELECT id FROM stock_quant_package WHERE id IN %s ORDER BY id FOR UPDATE',
                                [tuple(sorted(tags.ids))])
            tags.invalidate_recordset()

    def action_step_packing_validate(self):
        self._lock_process()
        return super(PackingProduction, self.with_context(_packing_control=_INTERNAL)).action_step_packing_validate()

    def action_prepare_materials(self):
        self._lock_process()
        with self.env.cr.savepoint():
            return self._prepare_materials()

    def _prepare_materials(self):
        for record in self:
            if record.state not in ('created', 'validated') or record.material_review_state == 'approved':
                raise UserError(_('Solo se preparan materiales de una OT abierta sin aprobación.'))
            record.material_line_ids.with_context(_packing_control=_INTERNAL).unlink()
            export_tags = record.step_packing_output_tag_ids.filtered(
                lambda tag: tag.step_tag_kind == 'E' and tag.step_packing_result == 'export')
            raw_products = record.raw_product_id | record.step_packing_input_tag_ids.step_tag_line_ids.product_id
            export_products = export_tags.step_tag_line_ids.product_id - raw_products
            planned_product = record.product_id - raw_products
            for tag in export_tags:
                total_boxes = sum(tag.step_tag_line_ids.mapped('boxes'))
                for detail in tag.step_tag_line_ids:
                    product, quantity = detail.product_id, detail.quantity
                    if product in raw_products:
                        product = (tag.step_packaging_id.product_id - raw_products) or planned_product or export_products
                        if len(product) != 1 or detail.boxes <= 0:
                            raise UserError(_('Identifique el producto terminado y las cajas de la tarja %s para preparar sus materiales.') % tag.name)
                        quantity = detail.boxes
                    bom = (record.bom_id if record.bom_id.product_tmpl_id == product.product_tmpl_id
                           and (not record.bom_id.product_id or record.bom_id.product_id == product)
                           else self.env['mrp.bom']._bom_find(product, company_id=record.company_id.id).get(product))
                    if not bom:
                        raise UserError(_('Configure una lista de materiales para %s.') % product.display_name)
                    factor = product.uom_id._compute_quantity(quantity, bom.product_uom_id) / bom.product_qty
                    for component in bom.bom_line_ids:
                        pallet_share = detail.boxes / total_boxes if total_boxes else 0
                        qty = component.product_uom_id._compute_quantity(
                            component.product_qty * factor + component.step_export_qty_per_pallet * pallet_share,
                            component.product_id.uom_id)
                        self.env['step.packing.material.consumption'].with_context(_packing_control=_INTERNAL).create({
                            'production_id': record.id, 'package_id': tag.id, 'product_id': component.product_id.id,
                            'planned_qty': qty, 'quantity': qty,
                        })
            record.with_context(_packing_control=_INTERNAL).write({
                'material_review_state': 'review', 'material_signature': record._material_signature()})
        return True

    def action_approve_materials(self):
        if not self.env.user.has_group('stock.group_stock_manager'):
            raise UserError(_('La aprobación requiere un administrador de Inventario.'))
        self._lock_process()
        for record in self:
            if record.state not in ('created', 'validated') or record.material_review_state != 'review':
                raise UserError(_('Prepare y revise los materiales antes de aprobar.'))
            if record.material_signature != record._material_signature():
                raise UserError(_('Cambió el detalle de las tarjas; vuelva a preparar los materiales.'))
            if any(line.quantity != line.planned_qty and not (line.reason or '').strip() for line in record.material_line_ids):
                raise ValidationError(_('Indique el motivo de cada ajuste de consumo.'))
            record.with_context(_packing_control=_INTERNAL).write({
                'material_review_state': 'approved', 'material_approved_by': self.env.uid,
                'material_approved_at': fields.Datetime.now(),
            })
        return True

    def action_reopen_materials(self):
        self._lock_process()
        if any(record.state not in ('created', 'validated') for record in self):
            raise UserError(_('No se reabren materiales de una OT cerrada.'))
        self.with_context(_packing_control=_INTERNAL).write({
            'material_review_state': 'review', 'material_approved_by': False, 'material_approved_at': False,
        })
        return True

    def action_reopen_quadrature(self):
        self._lock_process()
        if any(row.state != 'validated' or row.material_review_state == 'approved' for row in self):
            raise UserError(_('Solo se corrige una OT validada; reabra primero sus materiales aprobados.'))
        self.with_context(_packing_control=_INTERNAL).write({'state': 'created'})
        return True

    def action_reopen_close(self):
        if not self.env.user.has_group('stock.group_stock_manager'):
            raise UserError(_('Solo un administrador de Inventario puede revertir el cierre.'))
        self._lock_process()
        with self.env.cr.savepoint():
            for order in self:
                order._reverse_packing_close()
        return True

    def _reverse_packing_close(self):
        self.ensure_one()
        if self.state != 'closed' or self.cost_ids or self.purchase_bill_id or self.landed_cost_id or self.return_picking_id:
            raise UserError(_('La OT debe estar cerrada y sin costeo, factura, capitalización ni devolución.'))
        pickings = self.output_picking_id | self.material_picking_id | self.input_picking_id
        if not self.output_picking_id or not self.input_picking_id or any(
                picking.state != 'done' or picking.company_id != self.company_id for picking in pickings):
            raise UserError(_('No se encontraron todos los movimientos originales de cierre de esta OT.'))
        moves = pickings.move_ids.filtered(lambda move: move.state != 'cancel')
        if (moves.sudo().account_move_ids.filtered(lambda entry: entry.state != 'cancel')
                or moves.returned_move_ids.filtered(lambda move: move.state != 'cancel')
                or moves.move_dest_ids.filtered(lambda move: move.state != 'cancel')):
            raise UserError(_('Los movimientos de cierre tienen asientos, devoluciones o movimientos posteriores.'))
        output = self.step_packing_output_tag_ids
        inputs = self.step_packing_input_tag_ids
        if (not output or not inputs or any(tag.step_tag_state != 'validated' for tag in output)
                or any(tag.step_tag_state != 'processed' for tag in inputs)):
            raise UserError(_('Las tarjas ya no conservan el estado generado por este cierre.'))
        history = self.env['stock.move.line'].sudo().search_count([
            ('state', '!=', 'cancel'), ('id', '>', max(self.output_picking_id.move_line_ids.ids, default=0)),
            '|', ('package_id', 'in', output.ids), ('result_package_id', 'in', output.ids),
        ], limit=1)
        if (history or output.sudo().step_export_shipment_ids or output.sudo().step_reserved_ids
                or self.env['step.packing.inspection'].sudo().search_count([('production_id', '=', self.id)], limit=1)):
            raise UserError(_('Las tarjas tienen movimientos posteriores, embarques, reservas o inspecciones.'))
        if any(quant.quantity or quant.reserved_quantity for quant in inputs.quant_ids):
            raise UserError(_('Una tarja de entrada ya tiene existencias o reservas.'))
        if (self.output_picking_id.move_line_ids.result_package_id != output
                or self.input_picking_id.move_line_ids.package_id != inputs
                or self.material_picking_id.move_line_ids.package_id
                or self.material_picking_id.move_line_ids.result_package_id):
            raise UserError(_('Los movimientos originales no coinciden con las tarjas de la OT.'))
        self._check_close_output_stock(output)

        from .contract_valuation import _VALUATION
        order = self.with_context(_packing_control=_INTERNAL, _packing_valuation=_VALUATION)
        order.write({'valuation_snapshot': False})
        reversals = self.env['stock.picking']
        for picking in pickings:
            reversals |= order._reverse_close_picking(picking)
        if reversals.move_ids.sudo().account_move_ids:
            raise UserError(_('La reversión generaría asientos de inventario. Revise el cierre con Contabilidad.'))
        inputs.write({'step_tag_state': 'validated'})
        output.write({'step_tag_state': 'created'})
        order.write({
            'state': 'validated', 'input_picking_id': False, 'output_picking_id': False,
            'material_picking_id': False, 'material_review_state': 'review',
            'material_approved_by': False, 'material_approved_at': False,
            'step_close_reversal_ids': [Command.link(picking.id) for picking in reversals],
        })

    def _check_close_output_stock(self, output):
        expected = defaultdict(float)
        actual = defaultdict(float)
        for line in self.output_picking_id.move_line_ids:
            key = (line.result_package_id, line.product_id, line.location_dest_id, line.lot_id, line.owner_id)
            expected[key] += line.product_uom_id._compute_quantity(line.quantity, line.product_id.uom_id)
        for quant in output.quant_ids:
            if quant.reserved_quantity:
                raise UserError(_('Libere las reservas antes de revertir el cierre.'))
            key = (quant.package_id, quant.product_id, quant.location_id, quant.lot_id, quant.owner_id)
            actual[key] += quant.quantity
        for key in expected.keys() | actual.keys():
            if float_compare(actual[key], expected[key], precision_rounding=key[1].uom_id.rounding):
                raise UserError(_('Las existencias de salida deben coincidir con el movimiento de cierre.'))

    def _reverse_close_picking(self, picking):
        moves = picking.move_ids.filtered(lambda move: move.state == 'done')
        origins = {move.product_id.id: move.id for move in moves}
        lines = picking.move_line_ids.filtered(lambda line: line.move_id in moves and line.quantity > 0)
        if (not lines or len(origins) != len(moves)
                or any(line.location_id != picking.location_id or line.location_dest_id != picking.location_dest_id
                       for line in lines)):
            raise UserError(_('El traslado original no tiene una estructura de cierre reversible.'))
        items = [(line.product_id, line.product_uom_id._compute_quantity(line.quantity, line.product_id.uom_id),
                  line.result_package_id, line.package_id, line.lot_id, line.owner_id) for line in lines]
        warehouse = picking.picking_type_id.warehouse_id
        reversal = self.with_context(_packing_close_reversal=(_REVERSAL, origins))._create_packing_move(
            warehouse, picking.location_dest_id, picking.location_id, items)
        reversal.write({'return_id': picking.id})
        return reversal

    def _consume_packaging_materials(self, warehouse, location, production_location):
        self.ensure_one()
        grouped = defaultdict(float)
        for line in self.material_line_ids:
            grouped[line.product_id] += line.quantity
        return (self._create_packing_move(warehouse, location, production_location,
                [(product, qty, False, False) for product, qty in grouped.items() if qty > 0])
                if grouped else self.env['stock.picking'])

    def _create_packing_move(self, warehouse, source, dest, lines):
        if source.usage == 'internal':
            allocated = defaultdict(float)
            exact = []
            for line in lines:
                product, qty, package, result = line[:4]
                domain = [('product_id', '=', product.id), ('location_id', '=', source.id),
                          ('package_id', '=', package.id if package else False), ('quantity', '>', 0),
                          ('company_id', '=', self.company_id.id)]
                if len(line) == 6:
                    domain += [('lot_id', '=', line[4].id if line[4] else False),
                               ('owner_id', '=', line[5].id if line[5] else False)]
                elif not package:
                    domain.append(('owner_id', '=', False))
                quants = self.env['stock.quant'].search(domain, order='in_date, id')
                if quants:
                    self.env.cr.execute('SELECT id FROM stock_quant WHERE id IN %s ORDER BY id FOR UPDATE', [tuple(sorted(quants.ids))])
                    quants.invalidate_recordset()
                remaining = qty
                for quant in quants:
                    take = min(remaining, max(0, quant.quantity - quant.reserved_quantity - allocated[quant.id]))
                    if take <= 0:
                        continue
                    allocated[quant.id] += take
                    exact.append((product, take, package, result, quant.lot_id, quant.owner_id))
                    remaining -= take
                    if float_compare(remaining, 0, precision_rounding=product.uom_id.rounding) <= 0:
                        break
                if float_compare(remaining, 0, precision_rounding=product.uom_id.rounding) > 0:
                    raise UserError(_('Stock libre insuficiente de %(product)s en %(location)s. '
                                      'Cantidad requerida: %(required)s %(unit)s; faltante: %(missing)s. '
                                      'Revise el stock de esta ubicación y sus reservas.') % {
                                          'product': product.display_name, 'location': source.display_name,
                                          'required': qty, 'missing': remaining, 'unit': product.uom_id.display_name})
            lines = exact
        return super()._create_packing_move(warehouse, source, dest, lines)

    def action_step_packing_close(self):
        self._lock_process()
        if any(record.material_review_state != 'approved' for record in self):
            raise UserError(_('Revise y apruebe los materiales antes del cierre.'))
        if any(record.material_signature != record._material_signature() for record in self):
            raise UserError(_('Cambió el detalle de las tarjas; reabra y prepare los materiales.'))
        # All inventory changes roll back together even if a caller catches the failure.
        with self.env.cr.savepoint():
            return super(PackingProduction, self.with_context(_packing_control=_INTERNAL)).action_step_packing_close()

    def action_return_national_fruit(self):
        self._lock_process()
        with self.env.cr.savepoint():
            for record in self:
                if record.state != 'closed' or record.return_picking_id:
                    raise UserError(_('Solo se devuelve fruta de una OT cerrada sin devolución previa.'))
                tags = record.step_packing_output_tag_ids.filtered(lambda tag: tag.step_tag_kind == 'N')
                if not tags:
                    raise UserError(_('La OT no tiene fruta comercial, precalibre o desecho para devolver.'))
                if any(tag.step_tag_state != 'validated' for tag in tags):
                    raise UserError(_('Las tarjas nacionales deben estar validadas y disponibles.'))
                source = record._packing_stock_location(tags)
                warehouse = self.env['stock.warehouse'].search([('company_id', '=', record.company_id.id)], limit=1)
                destination = record.fruit_grower_id.with_company(record.company_id).property_stock_customer
                if not warehouse or destination.usage != 'customer':
                    raise UserError(_('Configure la bodega y la ubicación de cliente del productor.'))
                lines = [(quant.product_id, quant.quantity, tag, tag) for tag in tags
                         for quant in tag.quant_ids.filtered(lambda q: q.quantity > 0)]
                picking = record._create_packing_move(warehouse, source, destination, lines)
                picking.partner_id = record.fruit_grower_id
                tags.write({'step_tag_state': 'dispatched'})
                record.with_context(_packing_control=_INTERNAL).write({'return_picking_id': picking.id})
        return True

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('state', 'created') != 'created' or vals.get('material_review_state', 'pending') != 'pending' or vals.get('material_approved_by') or vals.get('material_approved_at') or vals.get('step_close_reversal_ids'):
                raise UserError(_('Las OT se crean pendientes de validación y revisión.'))
        return super().create(vals_list)

    def unlink(self):
        self._lock_process()
        if any(row.state != 'created' for row in self):
            raise UserError(_('No se elimina una OT validada o cerrada.'))
        return super().unlink()

    def write(self, vals):
        self._lock_process()
        internal = self.env.context.get('_packing_control') is _INTERNAL
        if not internal and {'state', 'input_picking_id', 'output_picking_id', 'material_picking_id', 'return_picking_id', 'step_close_reversal_ids'} & vals.keys():
            raise UserError(_('Use las acciones de validación y cierre para mover inventario.'))
        if not internal and {'material_review_state', 'material_approved_by', 'material_approved_at', 'material_signature'} & vals.keys():
            raise UserError(_('Use los botones de revisión y aprobación de materiales.'))
        protected = {'company_id', 'product_id', 'bom_id', 'step_packing_order_id',
                     'step_packing_input_tag_ids', 'step_packing_output_tag_ids', 'contract_id', 'required_inspection'}
        if protected & vals.keys() and any(record.state != 'created' for record in self):
            raise UserError(_('La cuadratura validada conserva sus productos, tarjas y planificación.'))
        if not internal and any(record.state in ('closed', 'costed', 'accounted') for record in self):
            raise UserError(_('Una OT cerrada no se modifica.'))
        if protected & vals.keys() and any(record.material_review_state == 'approved' for record in self):
            raise UserError(_('Reabra los materiales antes de cambiar productos o tarjas.'))
        return super().write(vals)


class MaterialConsumption(models.Model):
    _name = 'step.packing.material.consumption'
    _description = 'Consumo de material por tarja de salida'
    _check_company_auto = True

    production_id = fields.Many2one('step.packing.production', required=True, ondelete='cascade')
    company_id = fields.Many2one(related='production_id.company_id', store=True)
    package_id = fields.Many2one('stock.quant.package', string='Tarja', required=True)
    product_id = fields.Many2one('product.product', string='Material', required=True)
    uom_id = fields.Many2one(related='product_id.uom_id')
    planned_qty = fields.Float('Cantidad calculada', readonly=True, required=True)
    quantity = fields.Float('Consumo revisado', required=True)
    reason = fields.Char('Motivo del ajuste')

    def _check_editable(self):
        self.production_id._lock_process()
        if any(row.production_id.state not in ('created', 'validated') or
               row.production_id.material_review_state == 'approved' for row in self):
            raise UserError(_('Los materiales aprobados o consumidos no se modifican.'))

    @api.constrains('quantity', 'package_id', 'production_id')
    def _check_quantity(self):
        for row in self:
            if row.quantity < 0 or row.package_id not in row.production_id.step_packing_output_tag_ids:
                raise ValidationError(_('La cantidad debe ser no negativa y la tarja pertenecer a la OT.'))

    @api.model_create_multi
    def create(self, vals_list):
        if self.env.context.get('_packing_control') is not _INTERNAL:
            raise UserError(_('Prepare los materiales desde la OT; solo se ajusta el consumo y su motivo.'))
        parents = self.env['step.packing.production'].browse([row['production_id'] for row in vals_list])
        parents._lock_process()
        if any(row.state not in ('created', 'validated') or row.material_review_state == 'approved' for row in parents):
            raise UserError(_('No se agregan materiales a una OT aprobada o cerrada.'))
        return super().create(vals_list)

    def write(self, vals):
        self._check_editable()
        if {'production_id', 'package_id', 'product_id', 'planned_qty'} & vals.keys():
            raise UserError(_('Recalcule materiales para cambiar la tarja o el componente.'))
        return super().write(vals)

    def unlink(self):
        if self.env.context.get('_packing_control') is not _INTERNAL:
            raise UserError(_('Recalcule materiales desde la OT; no se elimina el consumo calculado manualmente.'))
        self._check_editable()
        return super().unlink()


class FruitPackageLine(models.Model):
    _inherit = 'step.fruit.package.line'

    lot_id = fields.Many2one('stock.lot', string='Lote de salida')

    @api.constrains('lot_id', 'product_id')
    def _check_lot(self):
        for line in self:
            if line.lot_id and line.lot_id.product_id != line.product_id:
                raise ValidationError(_('El lote debe corresponder al producto de la tarja.'))


class PackingDowntime(models.Model):
    _name = 'step.packing.downtime'
    _description = 'Detención de línea de packing'

    production_id = fields.Many2one('step.packing.production', required=True, ondelete='cascade')
    company_id = fields.Many2one(related='production_id.company_id', store=True)
    reason_id = fields.Many2one('step.packing.stop.reason', string='Causa', required=True)
    started_at = fields.Datetime('Inicio', required=True)
    finished_at = fields.Datetime('Término', required=True)
    comment = fields.Char('Observación')
    hours = fields.Float('Horas', compute='_compute_hours')

    @api.depends('started_at', 'finished_at')
    def _compute_hours(self):
        for record in self:
            record.hours = ((record.finished_at - record.started_at).total_seconds() / 3600
                            if record.started_at and record.finished_at else 0)

    @api.constrains('started_at', 'finished_at')
    def _check_period(self):
        for record in self:
            if record.finished_at <= record.started_at:
                raise ValidationError(_('La detención debe tener una duración positiva.'))
        self.production_id._check_times()

    def _check_editable(self):
        self.production_id._lock_process()
        if any(row.production_id.state not in ('created', 'validated') for row in self):
            raise UserError(_('Una OT cerrada conserva sus detenciones.'))

    @api.model_create_multi
    def create(self, vals_list):
        parents = self.env['step.packing.production'].browse([row['production_id'] for row in vals_list])
        parents._lock_process()
        if any(row.state not in ('created', 'validated') for row in parents):
            raise UserError(_('No se agregan detenciones a una OT cerrada.'))
        return super().create(vals_list)

    def write(self, vals):
        self._check_editable()
        if 'production_id' in vals:
            raise UserError(_('La detención conserva su OT.'))
        return super().write(vals)

    def unlink(self):
        self._check_editable()
        return super().unlink()
