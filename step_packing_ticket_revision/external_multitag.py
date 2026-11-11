from collections import defaultdict

from odoo import _, api, Command, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools.float_utils import float_compare


IMPORT = object()


class ExternalPackingInput(models.Model):
    _name = 'step.external.packing.input'
    _description = 'Aplicación parcial de tarja C en una OT'
    _check_company_auto = True

    production_id = fields.Many2one('step.packing.production', required=True, ondelete='cascade', check_company=True)
    company_id = fields.Many2one(related='production_id.company_id', store=True)
    original_id = fields.Many2one('stock.quant.package', string='Tarja original', required=True, ondelete='restrict')
    source_id = fields.Many2one('stock.quant.package', string='Tarja disponible', required=True, ondelete='restrict')
    consumed_id = fields.Many2one('stock.quant.package', string='Tarja aplicada', ondelete='restrict')
    boxes = fields.Integer(string='Cajas aplicadas', required=True)
    kilos = fields.Float(string='Kilos calculados', digits='Stock Weight', required=True)
    reported_kg = fields.Float(string='Kilos del Excel', digits='Stock Weight')

    _sql_constraints = [
        ('production_source_unique', 'unique(production_id, source_id)', 'La tarja ya se incluyó en esta OT.'),
        ('positive_amounts', 'check(boxes > 0 and kilos > 0)', 'Ingrese cajas y kilos positivos.'),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        if self.env.context.get('_external_multitag') is not IMPORT:
            raise UserError(_('Importe las aplicaciones parciales mediante el asistente de procesos.'))
        return super().create(vals_list)

    def write(self, vals):
        if self.env.context.get('_external_multitag') is not IMPORT:
            raise UserError(_('Las aplicaciones parciales se registran mediante el proceso de Packing.'))
        return super().write(vals)


class ExternalPackingPackage(models.Model):
    _inherit = 'stock.quant.package'

    step_external_remainder_id = fields.Many2one('stock.quant.package', string='Saldo de la división', copy=False, readonly=True)
    step_external_completion_of_id = fields.Many2one('stock.quant.package', string='Pallet que completa',
        copy=False, readonly=True, index=True, ondelete='restrict')
    step_external_completed_id = fields.Many2one('stock.quant.package', string='Pallet consolidado',
        copy=False, readonly=True, ondelete='restrict')
    step_external_completion_source_ids = fields.One2many('stock.quant.package', 'step_external_completed_id',
        string='Tarjas que aportaron al pallet', readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        self._check_multitag_values(vals_list)
        return super().create(vals_list)

    def write(self, vals):
        self._check_multitag_values([vals])
        return super().write(vals)

    def _check_multitag_values(self, vals_list):
        protected = {'step_external_remainder_id', 'step_external_completion_of_id', 'step_external_completed_id'}
        if self.env.context.get('_external_multitag') is not IMPORT and any(protected & vals.keys() for vals in vals_list):
            raise UserError(_('Use el proceso de Packing para registrar el origen y destino de la tarja.'))

    @api.depends('step_external_completed_id')
    def _compute_display_name(self):
        super()._compute_display_name()
        for tag in self.filtered('step_external_completed_id'):
            tag.display_name = _('%s (aporte histórico)', tag.display_name)

    def _lock_external_packages(self):
        if self:
            self.env.cr.execute('SELECT id FROM stock_quant_package WHERE id IN %s ORDER BY id FOR UPDATE',
                                [tuple(self.ids)])
            self.invalidate_recordset()

    def _check_external_pallet_stock(self, company):
        self.ensure_one()
        if self.step_tag_state != 'validated' or self.step_external_completed_id:
            raise UserError(_('El pallet %s debe estar validado y vigente antes de completarlo.', self.name))
        if (self.sudo().step_reserved_ids or self.sudo().step_export_shipment_ids
                or self.sudo().step_guide_ids or self.sudo().step_invoice_ids):
            raise UserError(_('El pallet %s ya tiene reservas o documentos de despacho.', self.name))
        quants = self.quant_ids.filtered(lambda quant: quant.quantity or quant.reserved_quantity)
        if quants:
            self.env.cr.execute('SELECT id FROM stock_quant WHERE id IN %s ORDER BY id FOR UPDATE', [tuple(quants.ids)])
            quants.invalidate_recordset()
        expected, actual = defaultdict(float), defaultdict(float)
        for line in self.step_tag_line_ids:
            expected[line.product_id, line.lot_id] += line.quantity
        for quant in quants:
            actual[quant.product_id, quant.lot_id] += quant.quantity
        if (not expected or not quants or len(quants.location_id) != 1 or quants.location_id.usage != 'internal'
                or any(q.company_id != company or q.reserved_quantity or q.quantity <= 0 for q in quants)
                or any(float_compare(actual[key], expected[key], precision_rounding=key[0].uom_id.rounding)
                       for key in actual.keys() | expected.keys())):
            raise UserError(_('El pallet %s debe conservar su stock completo y sin reservas.', self.name))
        return quants


class ExternalPackingDetail(models.Model):
    _inherit = 'step.fruit.package.line'

    step_external_source_ot_id = fields.Many2one(related='source_package_id.step_packing_production_id',
        string='OT del aporte')
    step_external_source_variety_id = fields.Many2one(related='source_package_id.variedad_id', string='Variedad de origen')


class ExternalPackingProduction(models.Model):
    _inherit = 'step.packing.production'

    step_external_input_ids = fields.One2many('step.external.packing.input', 'production_id',
        string='Consumo parcial de tarjas C', copy=False, readonly=True)

    def write(self, vals):
        internal = self.env.context.get('_external_multitag') is IMPORT
        if 'step_external_input_ids' in vals and not internal:
            raise UserError(_('Las aplicaciones de tarjas C se registran en el importador de procesos.'))
        if internal or 'step_packing_input_tag_ids' not in vals or not self.step_external_input_ids:
            return super().write(vals)
        with self.env.cr.savepoint():
            result = super().write(vals)
            self._check_external_inputs()
            return result

    @api.depends('step_external_input_ids.kilos', 'step_external_input_ids.consumed_id')
    def _compute_packing_balance(self):
        super()._compute_packing_balance()
        for order in self:
            pending = order.step_external_input_ids.filtered(lambda row: not row.consumed_id)
            difference = sum(row.source_id.step_actual_kg - row.kilos for row in pending)
            order.step_packing_input_kg -= difference
            order.step_packing_loss_kg -= difference

    @api.depends('step_external_input_ids.boxes', 'step_external_input_ids.consumed_id')
    def _compute_fruit_metrics(self):
        super()._compute_fruit_metrics()
        for order in self.filtered('step_external_input_ids'):
            pending = order.step_external_input_ids.filtered(lambda row: not row.consumed_id)
            boxes = sum(order.step_packing_input_tag_ids.mapped('step_actual_boxes'))
            boxes -= sum(row.source_id.step_actual_boxes - row.boxes for row in pending)
            order.average_harvest_box_kg = order.step_packing_input_kg / boxes if boxes else 0

    def _check_external_inputs(self):
        for order in self:
            if any((row.consumed_id or row.source_id) not in order.step_packing_input_tag_ids
                   for row in order.step_external_input_ids):
                raise UserError(_('Conserve en la OT las tarjas C incluidas en el consumo parcial.'))

    def _check_packing_tags(self):
        self._check_external_inputs()
        return super()._check_packing_tags()

    def _check_external_completion(self, target, pallet_type, boxes, producer, species, fruit_type, packaging, caliber):
        self.ensure_one()
        target.check_access('write')
        target._lock_external_packages()
        target._check_external_pallet_stock(self.company_id)
        capacity = pallet_type.step_export_boxes_per_pallet
        if (target.step_tag_kind != 'E' or target.step_packing_result != 'export'
                or target.step_producer_id != producer or target.step_tag_line_ids.producer_id != producer
                or target.especie_id != species or target.fruit_type != fruit_type
                or target.step_tag_line_ids.product_id != packaging.product_id
                or target.fruit_caliber_id != caliber):
            raise UserError(_('El pallet %s debe coincidir en productor, especie, producto, tipo de fruta y calibre.', target.name))
        if (not capacity or (pallet_type.company_id and pallet_type.company_id not in self.company_id.parent_ids | self.company_id)
                or (target.package_type_id.step_export_boxes_per_pallet and target.package_type_id != pallet_type)):
            raise UserError(_('Seleccione el tipo de pallet con la capacidad aplicable a %s.', target.name))
        if (float_compare(target.step_actual_boxes, capacity, precision_digits=2) >= 0
                or float_compare(target.step_actual_boxes + boxes, capacity, precision_digits=2) > 0):
            raise UserError(_('El pallet %s está completo o el aporte supera su capacidad.', target.name))
        if self.env['stock.quant.package'].sudo().search_count([
                ('step_external_completion_of_id', '=', target.id),
                ('step_packing_production_id', '!=', self.id),
                ('step_packing_production_id.state', 'in', ('created', 'validated')),
        ], limit=1):
            raise UserError(_('Otra OT ya está completando el pallet %s.', target.name))

    def _external_completion_tags(self):
        self.ensure_one()
        return self.step_packing_output_tag_ids.filtered('step_external_completion_of_id')

    def _check_external_completion_tags(self):
        self.ensure_one()
        components = self._external_completion_tags()
        if len(components) != len(components.step_external_completion_of_id):
            raise UserError(_('Incluya un solo aporte por pallet en cada OT.'))
        components.step_external_completion_of_id._lock_external_packages()
        for tag in components:
            self._check_external_completion(tag.step_external_completion_of_id, tag.package_type_id,
                tag.step_actual_boxes, tag.step_producer_id, tag.especie_id, tag.fruit_type,
                tag.step_packaging_id, tag.fruit_caliber_id)

    def action_step_packing_validate(self):
        with self.env.cr.savepoint():
            self._lock_process()
            for order in self:
                order._check_external_completion_tags()
                for row in order.step_external_input_ids.filtered(lambda line: not line.consumed_id):
                    split = self.env['step.packing.tag.split'].with_context(_external_multitag=IMPORT).create({
                        'production_id': order.id, 'source_id': row.source_id.id,
                        'process_boxes': row.boxes, 'process_kg': row.kilos,
                    })
                    split.action_split()
                    children = self.env['stock.quant.package'].search([
                        ('company_id', '=', order.company_id.id),
                        ('step_tag_line_ids.source_package_id', '=', row.source_id.id),
                        ('name', 'in', [f'{row.source_id.name}-1', f'{row.source_id.name}-2']),
                    ])
                    used = children & order.step_packing_input_tag_ids
                    remaining = children - used
                    if len(used) != 1 or len(remaining) != 1:
                        raise ValidationError(_('No se pudieron identificar las dos partes de %s.', row.source_id.name))
                    row.source_id.with_context(_external_multitag=IMPORT).step_external_remainder_id = remaining
                    row.with_context(_external_multitag=IMPORT).consumed_id = used
            return super().action_step_packing_validate()

    def action_step_packing_close(self):
        with self.env.cr.savepoint():
            self._lock_process()
            for order in self:
                order._check_external_completion_tags()
            result = super().action_step_packing_close()
            for order in self:
                for component in order._external_completion_tags():
                    order._complete_external_pallet(component)
            return result

    def _complete_external_pallet(self, component):
        self.ensure_one()
        original = component.step_external_completion_of_id
        sources = original | component
        quants = original._check_external_pallet_stock(self.company_id) | component._check_external_pallet_stock(self.company_id)
        location = quants.location_id
        if len(location) != 1:
            raise UserError(_('El pallet %s y su aporte deben estar en la misma ubicación.', original.name))
        variants = (sources.variedad_id | sources.step_tag_line_ids.step_external_source_variety_id)
        detail_values = []
        repack_values = []
        for line in sources.step_tag_line_ids:
            values = {'producer_id': line.producer_id.id, 'product_id': line.product_id.id,
                      'quantity': line.quantity, 'boxes': line.boxes, 'kilos': line.kilos}
            detail_values.append(Command.create(dict(values, lot_id=line.lot_id.id,
                source_package_id=(line.source_package_id or line.package_id).id)))
            repack_values.append(dict(values, source_package_id=line.package_id.id))
        target = self.env['stock.quant.package'].create({
            'name': original.name, 'is_fruit_tag': True, 'step_tag_kind': 'E', 'step_packing_result': 'export',
            'step_producer_id': original.step_producer_id.id, 'fundo_id': original.fundo_id.id,
            'especie_id': original.especie_id.id, 'variedad_id': variants.id if len(variants) == 1 else False,
            'fruit_type': original.fruit_type, 'fruit_caliber_id': original.fruit_caliber_id.id,
            'fruit_category_id': original.fruit_category_id.id, 'fruit_quality_id': original.fruit_quality_id.id,
            'fruit_class_id': original.fruit_class_id.id, 'label': original.label,
            'step_packaging_id': original.step_packaging_id.id, 'package_type_id': component.package_type_id.id,
            'step_packing_line_id': component.step_packing_line_id.id,
            'step_export_season_id': original.step_export_season_id.id,
            'step_external_pallet_reference': original.step_external_pallet_reference,
            'step_external_pallet_export_kg': sum(sources.mapped('step_external_pallet_export_kg')),
            'box_count': round(sum(sources.mapped('step_actual_boxes'))), 'step_tag_line_ids': detail_values,
        })
        repack = self.env['step.packing.repack'].create({
            'company_id': self.company_id.id, 'date': self.date, 'packing_partner_id': self.packing_partner_id.id,
            'packing_line_id': self.step_packing_line_id.id, 'selected_source_ids': [Command.set(sources.ids)],
            'line_ids': [Command.create(dict(vals, target_package_id=target.id)) for vals in repack_values],
        })
        warehouse = self.output_picking_id.picking_type_id.warehouse_id
        picking = self._create_packing_move(warehouse, location, location, [
            (quant.product_id, quant.quantity, quant.package_id, target, quant.lot_id, quant.owner_id)
            for quant in quants
        ])
        sources.with_context(_external_multitag=IMPORT).write({
            'step_tag_state': 'repalletized', 'step_external_completed_id': target.id,
        })
        target.action_step_validate_tag()
        repack.write({'picking_id': picking.id, 'state': 'done'})
