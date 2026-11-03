from odoo import Command, api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_compare, float_round


class Production(models.Model):
    _inherit = 'step.packing.production'

    def _check_split_input(self):
        self.ensure_one()
        self.check_access('write')
        if self.state != 'created' or self.material_review_state == 'approved':
            raise UserError(_('Reabra la cuadratura y la aprobación de materiales antes de dividir la tarja.'))

    def action_split_input_tag(self):
        self._check_split_input()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Dividir tarja C'),
            'res_model': 'step.packing.tag.split',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_production_id': self.id},
        }


class TagSplit(models.TransientModel):
    _name = 'step.packing.tag.split'
    _description = 'Dividir una tarja C para consumo parcial'

    production_id = fields.Many2one('step.packing.production', required=True, readonly=True)
    input_tag_ids = fields.Many2many(related='production_id.step_packing_input_tag_ids')
    source_id = fields.Many2one('stock.quant.package', string='Tarja original', required=True)
    source_boxes = fields.Float(related='source_id.step_actual_boxes', string='Cajas originales')
    source_kg = fields.Float(related='source_id.step_actual_kg', string='Kilos originales')
    process_boxes = fields.Integer(string='Cajas a proceso', required=True)
    process_kg = fields.Float(string='Kilos a proceso', digits='Stock Weight', required=True)
    remaining_boxes = fields.Float(string='Cajas en stock', compute='_compute_remaining')
    remaining_kg = fields.Float(string='Kilos en stock', compute='_compute_remaining', digits='Stock Weight')

    @api.depends('source_boxes', 'source_kg', 'process_boxes', 'process_kg')
    def _compute_remaining(self):
        for wizard in self:
            wizard.remaining_boxes = wizard.source_boxes - wizard.process_boxes
            wizard.remaining_kg = wizard.source_kg - wizard.process_kg

    def action_split(self):
        self.ensure_one()
        self.check_access('read')
        ot, source = self.production_id, self.source_id
        with self.env.cr.savepoint():
            ot._lock_process()
            ot._check_split_input()
            source.check_access('write')
            if source not in ot.step_packing_input_tag_ids or source.step_tag_kind != 'C' or source.step_tag_state != 'validated':
                raise UserError(_('Seleccione una tarja C vigente de esta OT.'))
            if ot.sudo().search_count([('id', '!=', ot.id), ('step_packing_input_tag_ids', 'in', source.ids)], limit=1):
                raise UserError(_('Quite la tarja de las otras OT antes de dividirla.'))
            quants = source.quant_ids
            if quants:
                self.env.cr.execute('SELECT id FROM stock_quant WHERE id IN %s ORDER BY id FOR UPDATE', [tuple(quants.ids)])
                quants.invalidate_recordset()
            detail = source.step_tag_line_ids
            if (len(detail) != 1 or len(quants) != 1 or quants.company_id != ot.company_id
                    or quants.location_id.usage != 'internal' or quants.reserved_quantity
                    or quants.product_id != detail.product_id or quants.lot_id != detail.lot_id
                    or (quants.owner_id and quants.owner_id != detail.producer_id)):
                raise UserError(_('La división requiere una tarja con un solo detalle y existencias íntegras, sin reservas.'))
            uom = detail.product_id.uom_id
            if float_compare(quants.quantity, detail.quantity, precision_rounding=uom.rounding):
                raise UserError(_('Las existencias de la tarja no coinciden con su detalle.'))
            kilos = float_round(self.process_kg, precision_digits=2)
            if not 0 < self.process_boxes < detail.boxes or not 0 < kilos < detail.kilos:
                raise UserError(_('Las dos partes deben quedar con cajas y kilos positivos.'))
            # Preserve the actual stock unit. For weight products convert the
            # measured kilos. For unit products use the physical box fraction.
            kg_uom = self.env.ref('uom.product_uom_kgm')
            if uom.category_id == kg_uom.category_id:
                quantity = kg_uom._compute_quantity(kilos, uom, round=False)
            else:
                quantity = detail.quantity * self.process_boxes / detail.boxes
            rounded = float_round(quantity, precision_rounding=uom.rounding)
            if abs(rounded - quantity) > 1e-8 or not 0 < rounded < detail.quantity:
                raise UserError(_('La división no coincide con la unidad de inventario del producto.'))
            parts = ((rounded, self.process_boxes, kilos),
                     (detail.quantity - rounded, detail.boxes - self.process_boxes, detail.kilos - kilos))
            names = [f'{source.name}-{number}' for number in (1, 2)]
            for name in sorted(names):
                self.env.cr.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))', ['steps-process-tag:' + name])
            packages = self.env['stock.quant.package']
            if packages.sudo().search_count([('name', 'in', names)], limit=1):
                raise UserError(_('Ya existe una de las referencias de la división.'))
            metadata = {
                field: source[field].id if source._fields[field].type == 'many2one' else source[field]
                for field in (
                    'fundo_id', 'especie_id', 'variedad_id', 'fruit_type', 'fruit_quality_id',
                    'fruit_category_id', 'fruit_class_id', 'fruit_caliber_id', 'label',
                    'certificate', 'package_type_id', 'step_packaging_id', 'step_packing_result',
                    'step_producer_id', 'harvest_date', 'received_at', 'step_export_season_id',
                    'step_process_reception_id', 'packing_plant', 'step_packing_line_id',
                )
            }
            targets = packages.create([
                dict(metadata, name=name, is_fruit_tag=True, step_tag_kind='C', step_tag_state='created')
                for name in names
            ])
            repack = self.env['step.packing.repack'].with_company(ot.company_id).create({
                'company_id': ot.company_id.id,
                'selected_source_ids': [Command.set(source.ids)],
                'line_ids': [Command.create({
                    'source_package_id': source.id, 'target_package_id': target.id,
                    'producer_id': detail.producer_id.id, 'product_id': detail.product_id.id,
                    'quantity': qty, 'boxes': boxes, 'kilos': weight,
                }) for target, (qty, boxes, weight) in zip(targets, parts)],
            })
            repack.action_validate()
            ot.write({'step_packing_input_tag_ids': [Command.unlink(source.id), Command.link(targets[0].id)]})
        return {'type': 'ir.actions.act_window_close'}
