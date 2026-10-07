"""Operational controls: review materials per pallet before moving real stock."""
from collections import defaultdict
import hashlib
import json
from markupsafe import escape

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools.float_utils import float_compare

_INTERNAL = object()


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
            for tag in record.step_packing_output_tag_ids.filtered(lambda row: row.step_packing_result == 'export'):
                for detail in tag.step_tag_line_ids:
                    bom = (record.bom_id if record.bom_id.product_tmpl_id == detail.product_id.product_tmpl_id
                           else self.env['mrp.bom']._bom_find(detail.product_id, company_id=record.company_id.id).get(detail.product_id))
                    if not bom:
                        raise UserError(_('Configure una lista de materiales para %s.') % detail.product_id.display_name)
                    factor = detail.product_id.uom_id._compute_quantity(detail.quantity, bom.product_uom_id) / bom.product_qty
                    for component in bom.bom_line_ids:
                        total_boxes = sum(tag.step_tag_line_ids.mapped('boxes'))
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
                          ('package_id', '=', package.id if package else False), ('quantity', '>', 0)]
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
                    raise UserError(_('Stock libre insuficiente de %s; revise reservas y ubicación.') % product.display_name)
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
            if vals.get('state', 'created') != 'created' or vals.get('material_review_state', 'pending') != 'pending' or vals.get('material_approved_by') or vals.get('material_approved_at'):
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
        if not internal and {'state', 'input_picking_id', 'output_picking_id', 'material_picking_id', 'return_picking_id'} & vals.keys():
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
