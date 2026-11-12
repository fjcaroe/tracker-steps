import re
from collections import defaultdict
from odoo import _, api, Command, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools.float_utils import float_compare, float_is_zero
from odoo.addons.step_export_branch_consolidation.models import branch_companies

_INTERNAL = object()


class DispatchType(models.Model):
    _inherit = 'step.freight.dispatch.type'
    step_recipient_kind = fields.Selection([('customer', 'Cliente'), ('producer', 'Productor'),
        ('interplant', 'Empresa / sucursal relacionada')], string='Tipo de destinatario')


class Guide(models.Model):
    _inherit = 'step.dispatch.guide'
    step_recipient_kind = fields.Selection(related='dispatch_type_id.step_recipient_kind')
    step_recipient_domain = fields.Json(compute='_compute_recipient_domain')
    step_destination_company_id = fields.Many2one('res.company', compute='_compute_destination')
    step_destination_warehouse_id = fields.Many2one('stock.warehouse', string='Almacén de destino',
        domain="[('company_id','=',step_destination_company_id)]")
    step_source_warehouse_id = fields.Many2one('stock.warehouse', string='Almacén de origen',
        check_company=True, domain="[('company_id','=',company_id)]")
    step_destination_picking_id = fields.Many2one('stock.picking', string='Recepción de destino',
        readonly=True, copy=False, ondelete='restrict')

    @api.depends('company_id', 'dispatch_type_id.step_recipient_kind')
    @api.depends_context('uid', 'allowed_company_ids')
    def _compute_recipient_domain(self):
        for guide in self:
            kind = guide.step_recipient_kind
            guide.step_recipient_domain = ([('id', 'in',
                (branch_companies(self.env, guide.company_id) - guide.company_id).partner_id.ids)]
                if kind == 'interplant' else [('customer_rank', '>', 0)] if kind == 'customer'
                else [('is_productor', '=', True)] if kind == 'producer' else [])

    @api.depends('partner_id', 'dispatch_type_id', 'company_id')
    def _compute_destination(self):
        for guide in self:
            guide.step_destination_company_id = (branch_companies(self.env, guide.company_id) - guide.company_id).filtered(
                lambda company: company.partner_id == guide.partner_id)[:1] if guide.step_recipient_kind == 'interplant' else False

    @api.onchange('partner_id', 'dispatch_type_id', 'company_id')
    def _onchange_interplant_destination(self):
        for guide in self:
            warehouses = self.env['stock.warehouse'].search([('company_id', '=', guide.step_destination_company_id.id)]) if guide.step_destination_company_id else self.env['stock.warehouse']
            if guide.step_destination_warehouse_id not in warehouses:
                guide.step_destination_warehouse_id = warehouses if len(warehouses) == 1 else False

    @api.constrains('partner_id', 'dispatch_type_id', 'company_id', 'step_destination_warehouse_id')
    def _check_recipient(self):
        for guide in self.filtered(lambda g: g.state == 'draft'):
            if guide.partner_id and guide.step_recipient_domain and not self.env['res.partner'].search_count(
                    [('id', '=', guide.partner_id.id)] + guide.step_recipient_domain):
                raise ValidationError(_('El destinatario no corresponde al tipo de despacho seleccionado.'))
            if guide.step_destination_warehouse_id and guide.step_destination_warehouse_id.company_id != guide.step_destination_company_id:
                raise ValidationError(_('El almacén debe pertenecer a la planta destinataria.'))

    def _free_stock_tag(self, tag):
        self.ensure_one()
        quants = tag.quant_ids.filtered(lambda q: not float_is_zero(q.quantity, precision_rounding=q.product_id.uom_id.rounding))
        return (tag.is_fruit_tag and tag.step_tag_kind in ('C', 'E', 'N')
            and tag.step_tag_state == 'validated' and tag.company_id == self.company_id
            and quants and all(q.location_id.usage == 'internal' and q.company_id == self.company_id
                and q.quantity > 0 and not q.reserved_quantity for q in quants)
            and not tag.step_reserved_ids)

    @api.depends('dispatch_instruction_id', 'load_tag_ids', 'company_id')
    def _available_tags(self):
        planned = self.filtered('dispatch_instruction_id')
        super(Guide, planned)._available_tags()
        for guide in self - planned:
            used = self.search([('state', '!=', 'cancelled'), ('id', '!=', guide._origin.id or 0)]).load_tag_ids
            tags = self.env['stock.quant.package'].search([('is_fruit_tag', '=', True),
                ('step_tag_state', '=', 'validated'), ('company_id', '=', guide.company_id.id)])
            guide.available_load_tag_ids = tags.filtered(lambda tag: tag not in used and guide._free_stock_tag(tag)) | guide.load_tag_ids

    def _validate_load(self):
        super(Guide, self.filtered('dispatch_instruction_id'))._validate_load()
        for guide in self.filtered(lambda g: not g.dispatch_instruction_id and g.load_tag_ids):
            if guide.picking_id.state == 'done':
                continue  # completed loads are immutable and no longer have source stock
            self.env.cr.execute('SELECT id FROM stock_quant_package WHERE id IN %s ORDER BY id FOR UPDATE', [tuple(sorted(guide.load_tag_ids.ids))])
            guide.load_tag_ids.invalidate_recordset()
            if self.search_count([('id', '!=', guide.id), ('state', '!=', 'cancelled'), ('load_tag_ids', 'in', guide.load_tag_ids.ids)]):
                raise ValidationError(_('Una tarja ya está asignada a otra guía vigente.'))
            if any(not guide._free_stock_tag(tag) for tag in guide.load_tag_ids):
                raise ValidationError(_('Seleccione tarjas C, E o N vigentes, con todo su stock libre en la empresa de origen.'))

    def _sync_load(self):
        return super(Guide, self.filtered('dispatch_instruction_id'))._sync_load()

    @api.onchange('scan_code')
    def _scan(self):
        if self.dispatch_instruction_id:
            return super()._scan()
        for code in filter(None, (code.strip() for code in re.split(r'[\n,;]+', self.scan_code or ''))):
            tags = self.available_load_tag_ids.filtered(lambda tag: tag.name == code)
            if len(tags) != 1:
                raise UserError(_('Folio no disponible o ambiguo: %s', code))
            self.load_tag_ids |= tags
        self.scan_code = False

    @api.model_create_multi
    def create(self, values):
        if self.env.context.get('_step_interplant') is not _INTERNAL and any(v.get('step_destination_picking_id') for v in values):
            raise AccessError(_('La recepción se genera al confirmar el despacho.'))
        return super().create(values)

    def write(self, values):
        if self.env.context.get('_step_interplant') is not _INTERNAL:
            if 'step_destination_picking_id' in values:
                raise AccessError(_('La recepción vinculada se conserva.'))
            if any(g.picking_id.state == 'done' for g in self) and set(values) & {
                    'partner_id', 'dispatch_type_id', 'step_destination_warehouse_id', 'step_source_warehouse_id',
                    'picking_id', 'line_ids', 'state', 'company_id'}:
                raise UserError(_('El despacho tiene stock entregado. Conserve la guía y use una devolución de Inventario.'))
        return super().write(values)

    def action_confirm(self):
        with self.env.cr.savepoint():
            for guide in self.sorted('id'):
                self.env.cr.execute('SELECT id FROM step_dispatch_guide WHERE id=%s FOR UPDATE', [guide.id])
                guide.invalidate_recordset()
                if guide.state == 'confirmed':
                    continue
                guide._check_recipient()
                guide._validate_load()
                if guide.step_recipient_kind == 'interplant' and guide.dispatch_instruction_id:
                    raise UserError(_('Use el traslado interplanta sin instructivo de exportación.'))
                super(Guide, guide).action_confirm()
                if not guide.dispatch_instruction_id and (guide.load_tag_ids or guide.step_recipient_kind == 'interplant'):
                    guide._dispatch_stock()
        return True

    def _dispatch_stock(self):
        self.ensure_one()
        if self.picking_id:
            raise UserError(_('La guía ya tiene una operación de inventario; revísela antes de confirmar.'))
        company = self.company_id
        if company not in self.env.companies:
            raise AccessError(_('Active la empresa de origen.'))
        source = self.with_company(company).with_context(_step_interplant=_INTERNAL)
        tags = source.load_tag_ids
        locations = tags.quant_ids.filtered(lambda q: q.quantity > 0).location_id
        warehouse = self.step_source_warehouse_id
        if not warehouse and len(locations) == 1:
            warehouse = locations.warehouse_id
        if not warehouse:
            warehouses = self.env['stock.warehouse'].search([('company_id', '=', company.id)])
            warehouse = warehouses if len(warehouses) == 1 else warehouses.browse()
        if not warehouse or warehouse.company_id != company:
            raise UserError(_('Seleccione el almacén de origen.'))
        if tags and (len(locations) != 1 or locations.warehouse_id != warehouse):
            raise UserError(_('Despache tarjas de una misma ubicación y almacén por guía.'))
        destination = self.env.ref('stock.stock_location_customers')
        picking = source.env['stock.picking'].create({'company_id': company.id,
            'picking_type_id': warehouse.out_type_id.id, 'location_id': (locations or warehouse.lot_stock_id).id,
            'location_dest_id': destination.id, 'origin': self.name, 'step_dispatch_origin_guide_id': self.id})
        if tags:
            for tag in tags:
                for quant in tag.quant_ids.filtered(lambda q: q.quantity > 0):
                    move = source._new_move(picking, quant.product_id, quant.quantity)
                    source.env['stock.move.line'].create({'move_id': move.id, 'picking_id': picking.id,
                        'product_id': quant.product_id.id, 'product_uom_id': quant.product_id.uom_id.id,
                        'location_id': quant.location_id.id, 'location_dest_id': destination.id,
                        'package_id': tag.id, 'lot_id': quant.lot_id.id, 'owner_id': quant.owner_id.id,
                        'quantity': quant.quantity, 'picked': True})
        else:
            for line in self.line_ids:
                if not line.product_id.is_storable:
                    raise UserError(_('El traslado interplanta requiere productos almacenables.'))
                qty = line.product_uom_id._compute_quantity(line.quantity, line.product_id.uom_id)
                move = source._new_move(picking, line.product_id, qty)
                move._action_assign()
                if float_compare(move.quantity, qty, precision_rounding=line.product_id.uom_id.rounding):
                    raise UserError(_('No hay stock libre suficiente para %s.', line.product_id.display_name))
                move.picked = True
        picking.with_context(bypass_entire_pack=True).button_validate()
        if picking.state != 'done':
            raise UserError(_('Complete la salida de inventario antes de confirmar el traslado.'))
        self.with_context(_step_interplant=_INTERNAL).write({'picking_id': picking.id})
        if self.step_recipient_kind == 'interplant':
            self._create_destination_receipt(picking)
        tags.write({'step_tag_state': 'dispatched'})

    def _new_move(self, picking, product, quantity):
        move = picking.env['stock.move'].create({'name': product.display_name, 'picking_id': picking.id,
            'company_id': picking.company_id.id, 'product_id': product.id, 'product_uom': product.uom_id.id,
            'product_uom_qty': quantity, 'location_id': picking.location_id.id,
            'location_dest_id': picking.location_dest_id.id})
        move._action_confirm(merge=False)
        return move

    def _create_destination_receipt(self, outgoing):
        company = self.step_destination_company_id
        if not company or company not in branch_companies(self.env, self.company_id):
            raise AccessError(_('Seleccione una planta relacionada a la que tenga acceso.'))
        warehouse = self.step_destination_warehouse_id
        if not warehouse:
            candidates = self.env['stock.warehouse'].search([('company_id', '=', company.id)])
            warehouse = candidates if len(candidates) == 1 else candidates.browse()
        if not warehouse or warehouse.company_id != company:
            raise UserError(_('Seleccione el almacén de destino.'))
        scoped = self.with_company(company).with_context(_step_interplant=_INTERNAL)
        incoming = scoped.env['stock.picking'].create({'company_id': company.id,
            'picking_type_id': warehouse.in_type_id.id, 'location_id': self.env.ref('stock.stock_location_suppliers').id,
            'location_dest_id': warehouse.lot_stock_id.id, 'origin': self.name,
            'step_interplant_guide_id': self.id})
        tags, lots = {}, {}
        for line in outgoing.move_line_ids:
            product = line.product_id
            if product.company_id and product.company_id != company:
                raise UserError(_('El producto %s debe estar disponible en la planta de destino.', product.display_name))
            lot = scoped.env['stock.lot']
            if line.lot_id:
                if line.lot_id.id not in lots:
                    lots[line.lot_id.id] = scoped.env['stock.lot'].create({'name': line.lot_id.name,
                        'product_id': product.id, 'company_id': company.id, 'step_interplant_origin_lot_id': line.lot_id.id})
                lot = lots[line.lot_id.id]
            tag = scoped.env['stock.quant.package']
            original = line.package_id
            if original:
                if original.id not in tags:
                    tags[original.id] = scoped._copy_destination_tag(original, incoming)
                tag = tags[original.id]
            move = scoped._new_move(incoming, product, line.quantity_product_uom)
            scoped.env['stock.move.line'].create({'move_id': move.id, 'picking_id': incoming.id,
                'product_id': product.id, 'product_uom_id': product.uom_id.id,
                'location_id': incoming.location_id.id, 'location_dest_id': incoming.location_dest_id.id,
                'quantity': line.quantity_product_uom, 'lot_id': lot.id, 'owner_id': line.owner_id.id,
                'result_package_id': tag.id, 'step_interplant_origin_line_id': line.id})
        for old_id, tag in tags.items():
            original = outgoing.env['stock.quant.package'].browse(old_id)
            for detail in original.step_tag_line_ids:
                scoped.env['step.fruit.package.line'].create({'package_id': tag.id,
                    'producer_id': detail.producer_id.id, 'product_id': detail.product_id.id,
                    'quantity': detail.quantity, 'boxes': detail.boxes, 'kilos': detail.kilos,
                    'lot_id': lots[detail.lot_id.id].id if detail.lot_id else False})
        self.with_context(_step_interplant=_INTERNAL).write({'step_destination_picking_id': incoming.id})

    def _copy_destination_tag(self, original, incoming):
        self.env.cr.execute('SELECT pg_advisory_xact_lock(hashtext(%s))', [f'interplant:{incoming.company_id.id}:{original.name}'])
        if self.env['stock.quant.package'].search_count([('company_id', '=', incoming.company_id.id),
                ('name', '=', original.name), ('is_fruit_tag', '=', True), ('step_tag_state', 'not in', ['void', 'dispatched', 'processed', 'repalletized'])]):
            raise UserError(_('Ya existe una tarja vigente con el folio %s en destino.', original.name))
        names = ['name', 'package_type_id', 'step_tag_kind', 'step_producer_id', 'fundo_id', 'especie_id',
            'variedad_id', 'step_export_season_id', 'box_count', 'step_packaging_id', 'harvest_date',
            'fruit_type', 'fruit_category_id', 'fruit_caliber_id', 'label']
        values = {name: original[name].id if original._fields[name].type == 'many2one' else original[name] for name in names}
        values.update(is_fruit_tag=True, step_tag_state='created', company_id=incoming.company_id.id,
            step_process_reception_id=incoming.id, step_interplant_origin_tag_id=original.id)
        return self.env['stock.quant.package'].create(values)
