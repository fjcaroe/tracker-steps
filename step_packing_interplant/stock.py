from collections import Counter
from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.addons.step_agriculture_multicompany.models.producer_stock import _check_stock_company
from .dispatch import _INTERNAL


class AuditMixin(models.AbstractModel):
    _name = 'step.interplant.audit.mixin'
    _description = 'Origen inmutable de traslado interplanta'
    _interplant_audit_fields = ()

    @api.model_create_multi
    def create(self, values):
        if self.env.context.get('_step_interplant') is not _INTERNAL and any(
                any(v.get(name) or self.env.context.get('default_' + name) for name in self._interplant_audit_fields) for v in values):
            raise AccessError(_('El origen interplanta se genera desde la guía.'))
        return super().create(values)

    def write(self, values):
        if set(values) & set(self._interplant_audit_fields):
            raise AccessError(_('El origen del traslado se conserva.'))
        return super().write(values)


class Picking(models.Model):
    _name = 'stock.picking'
    _inherit = ['stock.picking', 'step.interplant.audit.mixin']
    _interplant_audit_fields = ('step_interplant_guide_id', 'step_dispatch_origin_guide_id')
    step_interplant_guide_id = fields.Many2one('step.dispatch.guide', string='Guía interplanta', readonly=True, copy=False, ondelete='restrict')
    step_dispatch_origin_guide_id = fields.Many2one('step.dispatch.guide', readonly=True, copy=False, ondelete='restrict')
    step_interplant_tag_ids = fields.Many2many('stock.quant.package', compute='_compute_interplant_tags', string='Tarjas recibidas')

    @api.depends('move_line_ids.result_package_id')
    def _compute_interplant_tags(self):
        for picking in self:
            picking.step_interplant_tag_ids = picking.move_line_ids.result_package_id.filtered('is_fruit_tag') if picking.step_interplant_guide_id else False

    def button_validate(self):
        with self.env.cr.savepoint():
            pending = self.filtered(lambda p: p.step_interplant_guide_id and p.state not in ('done', 'cancel'))
            for picking in pending:
                self.env.cr.execute('SELECT id FROM stock_picking WHERE id=%s FOR UPDATE', [picking.id])
                picking.invalidate_recordset()
                picking.check_access('write')
                if picking.company_id not in self.env.companies:
                    raise AccessError(_('Active la planta receptora para validar la llegada.'))
                # Immutable guide link created by the dispatcher: read its proof only.
                # The receiving user needs access to the destination, not source-company writes.
                guide = picking.step_interplant_guide_id.sudo()
                original = guide.picking_id
                lines = picking.move_line_ids
                checks = {
                    'recepción vinculada': picking == guide.step_destination_picking_id,
                    'salida realizada': original.state == 'done',
                    'guía confirmada': guide.state == 'confirmed',
                    'empresa de destino': picking.company_id == guide.step_destination_warehouse_id.company_id,
                    'tipo de operación': picking.picking_type_code == 'incoming',
                    'ubicación de origen': picking.location_id.usage == 'supplier',
                    'almacén de destino': not guide.step_destination_warehouse_id or picking.location_dest_id == guide.step_destination_warehouse_id.lot_stock_id,
                    'tipo de recepción': not picking.step_fruit_reception_kind,
                    'origen de las líneas': Counter(lines.step_interplant_origin_line_id.ids) == Counter(original.move_line_ids.ids),
                    'cantidad de líneas': len(lines) == len(original.move_line_ids),
                }
                invalid = [label for label, valid in checks.items() if not valid]
                if invalid:
                    raise UserError(_('La recepción difiere de la guía interplanta: %s.', ', '.join(invalid)))
                for line in lines:
                    origin = line.step_interplant_origin_line_id.sudo()
                    if (line.product_id != origin.product_id or line.owner_id != origin.owner_id
                            or abs(line.quantity_product_uom - origin.quantity_product_uom) > 0.000001
                            or line.result_package_id.step_interplant_origin_tag_id != origin.package_id
                            or bool(line.lot_id) != bool(origin.lot_id)
                            or line.lot_id and (line.lot_id.step_interplant_origin_lot_id != origin.lot_id
                                or line.lot_id.name != origin.lot_id.name
                                or line.lot_id.company_id != picking.company_id)):
                        raise UserError(_('Conserve producto, cantidad, lote, propietario y tarja del traslado.'))
                picking.step_interplant_tag_ids._check_interplant_content()
                lines.write({'picked': True})
            result = super().button_validate()
            for picking in pending.filtered(lambda p: p.state == 'done'):
                tags = picking.step_interplant_tag_ids
                tags.filtered(lambda tag: tag.step_tag_state == 'created').write({'received_at': fields.Datetime.now()})
                tags.filtered(lambda tag: tag.step_tag_state == 'created').action_step_validate_tag()
            return result

    def action_cancel(self):
        if self.filtered(lambda p: p.step_interplant_guide_id and p.step_interplant_guide_id.picking_id.state == 'done'):
            raise UserError(_('El traslado ya salió de origen. Registre la recepción y use una devolución de Inventario si debe retornarlo.'))
        return super().action_cancel()


class Package(models.Model):
    _name = 'stock.quant.package'
    _inherit = ['stock.quant.package', 'step.interplant.audit.mixin']
    _interplant_audit_fields = ('step_interplant_origin_tag_id',)
    step_interplant_origin_tag_id = fields.Many2one('stock.quant.package', string='Tarja de origen', readonly=True, copy=False, ondelete='restrict')

    def write(self, values):
        if any(tag.step_interplant_origin_tag_id for tag in self) and set(values) & {'step_process_reception_id', 'is_fruit_tag', 'name'}:
            raise AccessError(_('Conserve el folio y la recepción de origen de la tarja trasladada.'))
        return super().write(values)

    @api.constrains('company_id', 'fundo_id', 'fruit_category_id', 'fruit_class_id',
                    'fruit_quality_id', 'fruit_caliber_id', 'step_interplant_origin_tag_id')
    def _check_agricultural_masters(self):
        transferred = self.filtered('step_interplant_origin_tag_id')
        super(Package, self - transferred)._check_agricultural_masters()
        # A transferred pallet retains its original masters. This does not widen
        # their company assignments or allow selecting foreign masters manually.
        for tag in transferred:
            origin = tag.step_interplant_origin_tag_id.sudo()
            receipt = tag.step_process_reception_id
            guide = receipt.step_interplant_guide_id.sudo()
            if (not guide or origin not in guide.load_tag_ids or guide.company_id != origin.company_id
                    or receipt.company_id != tag.company_id or guide.company_id.root_id != tag.company_id.root_id):
                raise UserError(_('El origen del traslado no acredita los maestros de la tarja.'))
            for name in ('fundo_id', 'fruit_category_id', 'fruit_class_id', 'fruit_quality_id', 'fruit_caliber_id'):
                if tag[name] != origin[name]:
                    raise UserError(_('La tarja trasladada conserva los maestros de su origen.'))

    def _check_interplant_content(self):
        for tag in self.filtered('step_interplant_origin_tag_id'):
            origin = tag.step_interplant_origin_tag_id.sudo()
            names = ('name', 'step_tag_kind', 'step_producer_id', 'fundo_id', 'especie_id',
                     'variedad_id', 'step_packaging_id', 'box_count', 'step_export_season_id',
                     'fruit_category_id', 'fruit_class_id', 'fruit_quality_id', 'fruit_caliber_id')
            if any(tag[name] != origin[name] for name in names):
                raise UserError(_('Conserve los datos de la tarja de origen del traslado.'))
            expected = sorted((row.producer_id.id, row.product_id.id, row.lot_id.id or 0,
                row.quantity, row.boxes, row.kilos) for row in origin.step_tag_line_ids)
            actual = sorted((row.producer_id.id, row.product_id.id,
                row.lot_id.step_interplant_origin_lot_id.id or 0, row.quantity, row.boxes, row.kilos)
                for row in tag.step_tag_line_ids)
            if actual != expected:
                raise UserError(_('El detalle de las tarjas debe conservar lotes, cantidades, cajas y kilos de origen.'))

    def action_step_validate_tag(self):
        if any(tag.step_interplant_origin_tag_id and tag.step_process_reception_id.state != 'done' for tag in self):
            raise UserError(_('Valide la recepción interplanta para disponer de la tarja.'))
        return super().action_step_validate_tag()


class Lot(models.Model):
    _name = 'stock.lot'
    _inherit = ['stock.lot', 'step.interplant.audit.mixin']
    _interplant_audit_fields = ('step_interplant_origin_lot_id',)
    step_interplant_origin_lot_id = fields.Many2one('stock.lot', string='Lote de origen interplanta', readonly=True, copy=False, ondelete='restrict')

    def write(self, values):
        if any(lot.step_interplant_origin_lot_id for lot in self) and set(values) & {'name', 'product_id', 'company_id'}:
            raise AccessError(_('Conserve el código, producto y empresa del lote trasladado.'))
        return super().write(values)


def owner_matches(record, package):
    receipt = package.step_process_reception_id
    origin = package.step_interplant_origin_tag_id.sudo()
    guide = receipt.step_interplant_guide_id.sudo()
    if not (origin and guide and receipt.company_id == record.company_id
            and guide.company_id.root_id == record.company_id.root_id
            and origin in guide.load_tag_ids and origin.company_id == guide.company_id):
        return False
    return record.owner_id in guide.picking_id.move_line_ids.filtered(lambda line: line.package_id == origin).owner_id


class MoveLine(models.Model):
    _name = 'stock.move.line'
    _inherit = ['stock.move.line', 'step.interplant.audit.mixin']
    _interplant_audit_fields = ('step_interplant_origin_line_id',)
    step_interplant_origin_line_id = fields.Many2one('stock.move.line', readonly=True, copy=False, ondelete='restrict')

    def _check_company(self, fnames=None):
        return _check_stock_company(self, fnames, 'owner_id',
            lambda line: any(owner_matches(line, tag) for tag in line.package_id | line.result_package_id),
            lambda records, names: super(MoveLine, records)._check_company(names))


class Quant(models.Model):
    _inherit = 'stock.quant'

    def _check_company(self, fnames=None):
        return _check_stock_company(self, fnames, 'owner_id',
            lambda quant: owner_matches(quant, quant.package_id),
            lambda records, names: super(Quant, records)._check_company(names))
