from collections import defaultdict

from odoo import _, api, Command, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools.float_utils import float_compare

CONSERVATION = [('good', 'Buen estado'), ('repairable', 'Reparable'), ('bad', 'Mal estado')]
OPERATING = [('dirty', 'Sucio'), ('clean', 'Limpio'), ('sanitized', 'Sanitizado'), ('in_use', 'En uso')]


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    step_harvest_packaging_id = fields.Many2one(
        'product.packaging', string='Embalaje relacionado', ondelete='restrict',
        domain="[('step_packaging_group', '=', 'harvest'), ('company_id', 'in', [False, company_id])]",
        copy=False,
    )

    @api.constrains('step_harvest_packaging_id', 'step_is_harvest_container', 'company_id', 'is_storable')
    def _check_step_harvest_packaging(self):
        for template in self:
            packaging = template.step_harvest_packaging_id
            if not packaging:
                continue
            if (not template.step_is_harvest_container or not template.is_storable
                    or packaging.step_packaging_group != 'harvest'
                    or (packaging.company_id and template.company_id != packaging.company_id)):
                raise ValidationError(_('Asocie un embalaje de Cosecha de la misma empresa a un envase almacenable.'))
            self.env.cr.execute('SELECT id FROM product_packaging WHERE id = %s FOR UPDATE', [packaging.id])
            if self.sudo().with_context(active_test=False).search_count([
                    ('step_harvest_packaging_id', '=', packaging.id), ('company_id', '=', template.company_id.id),
                    ('id', '!=', template.id)]):
                raise ValidationError(_('Un embalaje de cosecha solo puede identificar un envase por empresa.'))


class ProductPackaging(models.Model):
    _inherit = 'product.packaging'

    @api.constrains('step_packaging_group', 'company_id')
    def _check_step_container_mapping(self):
        for packaging in self:
            self.env['product.template'].sudo().with_context(active_test=False).search(
                [('step_harvest_packaging_id', '=', packaging.id)])._check_step_harvest_packaging()

    def _step_physical_container(self, company):
        self.ensure_one()
        products = self.env['product.product'].search([
            ('step_harvest_packaging_id', '=', self.id), ('step_is_harvest_container', '=', True),
            ('company_id', 'in', [False, company.id]),
        ])
        products = products.filtered(lambda p: p.company_id == company) or products
        return products if len(products) == 1 else products.browse()


class StockLocation(models.Model):
    _inherit = 'stock.location'

    step_container_conservation = fields.Selection(CONSERVATION, string='Estado de conservación', copy=False)
    step_container_operating = fields.Selection(OPERATING, string='Estado operativo', copy=False)
    step_container_partner_id = fields.Many2one('res.partner', compute='_compute_step_container_partner',
                                               search='_search_step_container_partner', string='Productor / cliente')

    @api.depends('step_producer_id', 'step_container_operating', 'location_id.step_producer_id')
    def _compute_step_container_partner(self):
        for location in self:
            location.step_container_partner_id = location.step_producer_id or (
                location.location_id.step_producer_id if location.step_container_operating else False)

    @api.model
    def _search_step_container_partner(self, operator, value):
        roots = ('step_producer_id', operator, value)
        child = ('location_id.step_producer_id', operator, value)
        if (operator == '=' and not value) or (operator == '!=' and value) or operator == 'not in':
            return ['&', roots, '|', ('step_container_operating', '=', False), child]
        return ['|', roots, '&', ('step_container_operating', '!=', False), child]

    def _step_container_state_location(self, conservation, operating):
        self.ensure_one()
        if not (conservation and operating):
            return self
        self.env.cr.execute('SELECT id FROM stock_location WHERE id = %s FOR UPDATE', [self.id])
        location = self.with_context(active_test=False).search([
            ('location_id', '=', self.id), ('step_container_conservation', '=', conservation),
            ('step_container_operating', '=', operating), ('company_id', '=', self.company_id.id)], limit=1)
        if not location:
            # Location manager permissions are only bypassed for the fixed child generated here.
            location = self.sudo().create({
                'name': '%s / %s' % (dict(CONSERVATION)[conservation], dict(OPERATING)[operating]),
                'company_id': self.company_id.id, 'usage': 'internal', 'location_id': self.id,
                'step_container_conservation': conservation, 'step_container_operating': operating,
            }).sudo(False)
        if not location.active:
            raise UserError(_('La ubicación de ese estado está archivada: %s', location.display_name))
        return location

    @api.constrains('step_container_conservation', 'step_container_operating', 'usage')
    def _check_step_container_states(self):
        for location in self:
            if bool(location.step_container_conservation) != bool(location.step_container_operating) or (
                    location.step_container_operating and location.usage != 'internal'):
                raise ValidationError(_('Las ubicaciones de envases deben ser internas y tener ambos estados.'))

    def write(self, vals):
        if {'step_container_conservation', 'step_container_operating', 'location_id'} & vals.keys():
            for location in self.filtered('step_container_operating'):
                if any(vals.get(field, location[field].id if field == 'location_id' else location[field]) !=
                       (location[field].id if field == 'location_id' else location[field])
                       for field in {'step_container_conservation', 'step_container_operating', 'location_id'}):
                    raise UserError(_('Use un traslado para cambiar de estado; conserve la ubicación original.'))
        return super().write(vals)


class StockQuant(models.Model):
    _inherit = 'stock.quant'

    step_container_conservation = fields.Selection(related='location_id.step_container_conservation', store=True)
    step_container_operating = fields.Selection(related='location_id.step_container_operating', store=True)
    step_container_partner_id = fields.Many2one(related='location_id.step_container_partner_id')


class StockMoveLine(models.Model):
    _inherit = 'stock.move.line'

    step_container_source_partner_id = fields.Many2one(related='location_id.step_container_partner_id')
    step_container_dest_partner_id = fields.Many2one(related='location_dest_id.step_container_partner_id')
    step_container_source_conservation = fields.Selection(related='location_id.step_container_conservation')
    step_container_source_operating = fields.Selection(related='location_id.step_container_operating')
    step_container_conservation = fields.Selection(related='location_dest_id.step_container_conservation')
    step_container_operating = fields.Selection(related='location_dest_id.step_container_operating')


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def _step_move_containers(self, warehouse, source, destination, rows, origin, partner=None, strict=False, issue=False):
        """Reserve company stock, keeping the lot and the actual source location."""
        company = warehouse.company_id
        picking = self.with_company(company).create({
            'company_id': company.id, 'picking_type_id': warehouse.int_type_id.id,
            'location_id': source.id, 'location_dest_id': destination.id, 'origin': origin,
            'partner_id': partner.id if partner else False,
        })
        for product, quantity, lot, src, dst in sorted(rows, key=lambda row: (not row[2], row[3] == source)):
            if not product.is_storable or not product.step_is_harvest_container:
                raise ValidationError(_('Seleccione un envase de cosecha almacenable.'))
            if lot and (lot.product_id != product or (lot.company_id and lot.company_id != company)):
                raise ValidationError(_('El lote debe corresponder al envase y la empresa.'))
            if float_compare(quantity, 0, precision_rounding=product.uom_id.rounding) <= 0:
                raise ValidationError(_('La cantidad de envases debe ser positiva.'))
            move = picking.env['stock.move'].create({
                'picking_id': picking.id, 'company_id': company.id, 'name': product.display_name,
                'product_id': product.id, 'product_uom': product.uom_id.id, 'product_uom_qty': quantity,
                'location_id': src.id, 'location_dest_id': dst.id,
            })
            move._action_confirm(merge=False)
            move._do_unreserve()
            quants = self.env['stock.quant']._gather(product, src, lot_id=lot or None, strict=False)
            quants = quants.filtered(lambda quant: not quant.owner_id and (
                not strict or quant.location_id == src) and (not lot or quant.lot_id == lot) and (
                product.tracking == 'none' or quant.lot_id) and (
                not issue or not quant.location_id.step_container_operating or (
                    quant.location_id.step_container_conservation == 'good' and
                    quant.location_id.step_container_operating in ('clean', 'sanitized'))))
            remaining = quantity
            for location, item_lot, package in dict.fromkeys((quant.location_id, quant.lot_id, quant.package_id)
                                                              for quant in quants):
                remaining -= move._update_reserved_quantity(remaining, location, lot_id=item_lot,
                                                            package_id=package, strict=True)
                if float_compare(remaining, 0, precision_rounding=product.uom_id.rounding) <= 0:
                    break
            if issue and not dst.step_container_operating:
                for line in move.move_line_ids:
                    conservation = line.location_id.step_container_conservation
                    if conservation:
                        line.location_dest_id = dst._step_container_state_location(conservation, 'in_use')
            if float_compare(move.quantity, quantity, precision_rounding=product.uom_id.rounding) or any(
                    ml.owner_id or (lot and ml.lot_id != lot) or (product.tracking != 'none' and not ml.lot_id)
                    for ml in move.move_line_ids):
                raise UserError(_('No hay saldo libre de %(product)s en %(location)s para el lote o estado seleccionado.',
                                  product=product.display_name, location=src.display_name))
            move.picked = True
        picking.with_context(bypass_entire_pack=True).button_validate()
        if picking.state != 'done':
            raise UserError(_('No se pudo validar el traslado de envases.'))
        return picking

    def button_validate(self):
        candidates = self.filtered(lambda p: p.step_fruit_reception_kind and p.state not in ('done', 'cancel'))
        result = super().button_validate()
        for picking in candidates.filtered(lambda p: p.state == 'done'):
            picking._step_prepare_container_return()
        return result

    def _step_prepare_container_return(self):
        self.ensure_one()
        self.env.cr.execute('SELECT id FROM stock_picking WHERE id=%s FOR UPDATE', [self.id])
        self.invalidate_recordset(['step_container_transfer_ids'])
        existing = self.step_container_transfer_ids.filtered(lambda transfer: transfer.direction == 'return')[:1]
        if existing:
            return existing
        counts = defaultdict(float)
        for tag in self.fruit_tag_line_ids:
            product = tag.product_id.filtered('step_is_harvest_container')
            packaging = tag.packaging_id or tag.package_id.step_packaging_id
            quantity = tag.quantity if product else tag.box_count or (tag.quantity if tag.packaging_id else 0)
            if not product and packaging and packaging.step_packaging_group == 'harvest':
                product = packaging._step_physical_container(self.company_id)
            if product and quantity > 0:
                lot = tag.stock_lot_id if tag.stock_lot_id.product_id == product else False
                counts[(product.id, lot.id if lot else False)] += quantity
        if not counts or not self.fruit_fundo_id.partner_id or not self.picking_type_id.warehouse_id:
            return existing
        return self.env['step.harvest.container.transfer'].with_context(mail_create_nosubscribe=True).create({
            'direction': 'return', 'producer_id': self.fruit_fundo_id.partner_id.id,
            'fruit_picking_id': self.id, 'warehouse_id': self.picking_type_id.warehouse_id.id,
            'company_id': self.company_id.id,
            'line_ids': [Command.create({'product_id': product_id, 'lot_id': lot_id, 'quantity': quantity})
                         for (product_id, lot_id), quantity in counts.items()],
        })

    def action_step_container_return(self):
        action = super().action_step_container_return()
        draft = self._step_prepare_container_return()
        if draft:
            action['res_id'] = draft.id
        action['context']['default_warehouse_id'] = self.picking_type_id.warehouse_id.id
        return action


class Transfer(models.Model):
    _inherit = 'step.harvest.container.transfer'

    dispatch_guide_id = fields.Many2one('step.dispatch.guide', string='Guía de despacho', readonly=True,
                                       copy=False, index=True, ondelete='restrict', groups='stock.group_stock_user')

    _sql_constraints = [('step_container_guide_unique', 'unique(dispatch_guide_id)',
                         'La guía ya tiene un movimiento de envases.')]

    def action_validate(self):
        with self.env.cr.savepoint():
            for transfer in self.sorted('id'):
                transfer._step_validate_with_states()
        return True

    def _step_validate_with_states(self):
        self.ensure_one()
        self.check_access('write')
        self.env.cr.execute('SELECT id FROM step_harvest_container_transfer WHERE id = %s FOR UPDATE', [self.id])
        self.invalidate_recordset()
        if self.state != 'draft' or not self.line_ids:
            raise UserError(_('Agregue envases a un movimiento en borrador.'))
        if self.warehouse_id.company_id != self.company_id or (self.producer_id.company_id and
                                                              self.producer_id.company_id != self.company_id):
            raise ValidationError(_('El productor / cliente y la bodega deben estar disponibles en esta empresa.'))
        if self.fruit_picking_id:
            fruit = self.fruit_picking_id
            if fruit.company_id != self.company_id or fruit.state != 'done' or (
                    fruit.fruit_fundo_id.partner_id or fruit.partner_id) != self.producer_id:
                raise ValidationError(_('El documento de fruta debe estar validado y coincidir en empresa y productor.'))
        self.env.cr.execute('SELECT id FROM res_partner WHERE id = %s FOR UPDATE', [self.producer_id.id])
        partner = self.producer_id.sudo()._step_container_location(self.company_id).sudo(False)
        warehouse = self.warehouse_id.lot_stock_id
        source, destination = (warehouse, partner) if self.direction == 'issue' else (partner, warehouse)
        rows = []
        for line in self.line_ids:
            if line.source_location_id and line.source_location_id.location_id != source:
                raise ValidationError(_('El estado de origen debe estar en la bodega o cuenta de origen del movimiento.'))
            if bool(line.conservation) != bool(line.operating):
                raise ValidationError(_('Complete ambos estados de destino o deje ambos sin asignar.'))
            dst = destination._step_container_state_location(line.conservation, line.operating)
            rows.append((line.product_id, line.quantity, line.lot_id, line.source_location_id or source, dst))
        picking = self.env['stock.picking']._step_move_containers(
            self.warehouse_id, source, destination, rows, self.name, self.producer_id, issue=self.direction == 'issue')
        self.write({'picking_id': picking.id, 'state': 'done'})


class TransferLine(models.Model):
    _inherit = 'step.harvest.container.transfer.line'

    lot_id = fields.Many2one('stock.lot', string='Lote / serie', domain="[('product_id', '=', product_id)]")
    source_location_id = fields.Many2one('stock.location', string='Estado de origen',
                                        domain="[('step_container_operating', '!=', False)]")
    conservation = fields.Selection(CONSERVATION, string='Conservación de destino')
    operating = fields.Selection(OPERATING, string='Operación de destino')


class ContainerOpening(models.TransientModel):
    _inherit = 'step.harvest.container.opening'

    def action_apply(self):
        self.ensure_one()
        if not any(line.lot_id or line.conservation or line.operating for line in self.line_ids):
            return super().action_apply()
        if not self.env.user.has_group('stock.group_stock_manager'):
            raise UserError(_('El inventario inicial requiere permisos de administrador de Inventario.'))
        quants = self.env['stock.quant'].with_company(self.company_id)
        seen = set()
        pending = []
        for line in self.line_ids.sorted(lambda item: item.producer_id.id):
            product, lot = line.product_id, line.lot_id
            if not product.is_storable or not product.step_is_harvest_container or line.quantity < 0:
                raise ValidationError(_('Revise el envase y la cantidad del saldo inicial.'))
            if line.producer_id.company_id and line.producer_id.company_id != self.company_id:
                raise ValidationError(_('El destinatario no pertenece a esta empresa.'))
            if (product.tracking != 'none' and not lot) or (lot and (
                    lot.product_id != product or (lot.company_id and lot.company_id != self.company_id))):
                raise ValidationError(_('Seleccione el lote o serie del envase en esta empresa.'))
            if bool(line.conservation) != bool(line.operating):
                raise ValidationError(_('Complete ambos estados o deje ambos en blanco.'))
            self.env.cr.execute('SELECT id FROM res_partner WHERE id = %s FOR UPDATE', [line.producer_id.id])
            root = line.producer_id._step_container_location(self.company_id)
            key = (root.id, product.id, lot.id, line.conservation, line.operating)
            if key in seen:
                raise ValidationError(_('No repita el envase, lote y estado para el mismo destinatario.'))
            seen.add(key)
            if quants.search_count([
                    ('location_id', 'child_of', root.id), ('product_id', '=', product.id), ('lot_id', '=', lot.id)]):
                raise UserError(_('Ya existe historial para este envase y lote; use un ajuste de inventario.'))
            location = root._step_container_state_location(line.conservation, line.operating)
            pending.append({'product_id': product.id, 'lot_id': lot.id, 'location_id': location.id,
                            'inventory_quantity': line.quantity})
        if quants.with_context(inventory_mode=True).create(pending).action_apply_inventory():
            raise UserError(_('Revise los lotes, series y cantidades del inventario inicial.'))
        return {'type': 'ir.actions.act_window_close'}


class ContainerOpeningLine(models.TransientModel):
    _inherit = 'step.harvest.container.opening.line'

    lot_id = fields.Many2one('stock.lot', string='Lote / serie', domain="[('product_id', '=', product_id)]")
    conservation = fields.Selection(CONSERVATION, string='Conservación')
    operating = fields.Selection(OPERATING, string='Estado operativo')
