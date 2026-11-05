"""Review and consume pallet materials within the native repalletization transaction."""
from collections import defaultdict
import hashlib
import json

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from .material_tools import allocate_stock, create_stock_transfer, material_recipe, component_quantities

_MATERIAL = object()


class Company(models.Model):
    _inherit = 'res.company'

    step_packing_allow_material_shortage = fields.Boolean(
        string='Permitir consumo de materiales sin stock', default=True,
        help='Permite saldo negativo en los materiales de Packing y repaletizado si su costo es mayor a cero.',
    )


class Repack(models.Model):
    _inherit = 'step.packing.repack'

    consume_pallet_materials = fields.Boolean('Consumo de materiales de pallet', copy=False)
    material_line_ids = fields.One2many('step.packing.repack.material', 'repack_id', string='Materiales')
    material_picking_id = fields.Many2one('stock.picking', string='Consumo de materiales', readonly=True, copy=False, check_company=True)
    material_signature = fields.Char(copy=False, readonly=True)

    def _lock_material_repack(self):
        if not self:
            return
        self.check_access('write')
        self.env.cr.execute('SELECT id FROM step_packing_repack WHERE id IN %s ORDER BY id FOR UPDATE',
                            [tuple(sorted(self.ids))])
        self.invalidate_recordset()

    def _material_signature(self):
        self.ensure_one()
        recipes = []
        for line in self.line_ids.sorted('id'):
            if line.source_package_id.step_tag_kind != 'E':
                raise UserError(_('El consumo de materiales de pallet corresponde a tarjas de exportación.'))
            bom, product, quantity = material_recipe(
                line.source_package_id, line, self.company_id, line.source_package_id.step_packing_production_id)
            recipes.append((line.id, line.source_package_id.id, line.target_package_id.id,
                            product.id, quantity, line.boxes,
                            [(item.id, item.product_id.id, item.product_uom_id.id,
                              item.step_export_qty_per_pallet) for item in bom.bom_line_ids]))
        return hashlib.sha256(json.dumps(recipes).encode()).hexdigest()

    def action_prepare_materials(self):
        self._lock_material_repack()
        with self.env.cr.savepoint():
            for record in self:
                if record.state != 'draft' or not record.consume_pallet_materials or not record.line_ids:
                    raise UserError(_('Prepare materiales en un repaletizado creado con distribución y consumo activado.'))
                totals = defaultdict(float)
                for target in record.line_ids.target_package_id:
                    lines = record.line_ids.filtered(lambda row: row.target_package_id == target)
                    boxes = sum(lines.mapped('boxes'))
                    if boxes <= 0:
                        raise ValidationError(_('Las cajas de destino deben ser positivas.'))
                    for line in lines:
                        if line.source_package_id.step_tag_kind != 'E':
                            raise UserError(_('Los materiales de pallet se calculan para fruta de exportación.'))
                        bom, product, quantity = material_recipe(
                            line.source_package_id, line, record.company_id, line.source_package_id.step_packing_production_id)
                        for component, qty in component_quantities(
                                bom, product, quantity, line.boxes / boxes, include_boxes=False):
                            totals[(target.id, component.id)] += qty
                record.material_line_ids.with_context(_repack_material=_MATERIAL).unlink()
                self.env['step.packing.repack.material'].with_context(_repack_material=_MATERIAL).create([
                    {'repack_id': record.id, 'package_id': tag, 'product_id': product,
                     'planned_qty': qty, 'quantity': qty} for (tag, product), qty in totals.items()])
                record.with_context(_repack_material=_MATERIAL).write({'material_signature': record._material_signature()})
        return True

    def _packing_move_extra_values(self, product, qty, source, dest, lines):
        return {}

    def _create_repack_material_move(self):
        self.ensure_one()
        company = self.company_id
        warehouse = company.step_packing_warehouse_id if 'step_packing_warehouse_id' in company._fields else False
        warehouse = warehouse or self.env['stock.warehouse'].search([('company_id', '=', company.id)], limit=1)
        if not warehouse:
            raise UserError(_('Configure una bodega para consumir materiales.'))
        location = (company.step_packing_material_location_id
                    if 'step_packing_material_location_id' in company._fields else False) or warehouse.lot_stock_id
        destination = self.env['stock.location'].search([
            ('usage', '=', 'production'), ('company_id', '=', company.id)], limit=1)
        if not destination:
            raise UserError(_('Configure la ubicación de producción de la empresa.'))
        totals = defaultdict(float)
        for line in self.material_line_ids:
            totals[line.product_id] += line.quantity
        lines = [(product, qty, False, False) for product, qty in totals.items() if qty > 0]
        if not lines:
            return self.env['stock.picking']
        lines = allocate_stock(self, location, lines, company.step_packing_allow_material_shortage)
        return create_stock_transfer(self, warehouse, location, destination, lines)

    def action_validate(self):
        self._lock_material_repack()
        with self.env.cr.savepoint():
            for record in self:
                if record.consume_pallet_materials and record.material_signature != record._material_signature():
                    raise UserError(_('Prepare de nuevo los materiales; cambió la distribución o la matriz de pallet.'))
            result = super().action_validate()
            for record in self.filtered('consume_pallet_materials'):
                picking = record._create_repack_material_move()
                record.with_context(_repack_material=_MATERIAL).write({'material_picking_id': picking.id})
            return result

    @api.model_create_multi
    def create(self, vals_list):
        if any({'material_signature', 'material_picking_id'} & vals.keys() for vals in vals_list):
            raise UserError(_('Los materiales y su traslado se generan desde el repaletizado.'))
        return super().create(vals_list)

    def write(self, vals):
        self._lock_material_repack()
        internal = self.env.context.get('_repack_material') is _MATERIAL
        if {'material_signature', 'material_picking_id'} & vals.keys() and not internal:
            raise UserError(_('Use las acciones de materiales del repaletizado.'))
        if {'consume_pallet_materials', 'material_line_ids'} & vals.keys() and any(r.state != 'draft' for r in self):
            raise UserError(_('Los materiales de un repaletizado validado se conservan.'))
        return super().write(vals)


class Material(models.Model):
    _name = 'step.packing.repack.material'
    _description = 'Consumo de material por pallet de repaletizado'
    _check_company_auto = True

    repack_id = fields.Many2one('step.packing.repack', required=True, ondelete='cascade')
    company_id = fields.Many2one(related='repack_id.company_id', store=True)
    package_id = fields.Many2one('stock.quant.package', string='Tarja de destino', required=True)
    product_id = fields.Many2one('product.product', string='Material', required=True)
    uom_id = fields.Many2one(related='product_id.uom_id', string='Unidad')
    planned_qty = fields.Float('Cantidad calculada', readonly=True, digits='Product Unit of Measure')
    quantity = fields.Float('Consumo', digits='Product Unit of Measure')

    @api.constrains('quantity', 'product_id', 'package_id', 'repack_id')
    def _check_material(self):
        for line in self:
            if line.quantity < 0 or line.package_id not in line.repack_id.line_ids.target_package_id:
                raise ValidationError(_('El consumo debe ser positivo o cero y corresponder a una tarja de destino.'))
            if line.product_id.company_id and line.product_id.company_id != line.company_id:
                raise ValidationError(_('El material debe pertenecer a la empresa del repaletizado.'))

    def _check_editable(self):
        self.repack_id._lock_material_repack()
        if any(line.repack_id.state != 'draft' for line in self):
            raise UserError(_('Los materiales validados no se modifican.'))

    @api.model_create_multi
    def create(self, vals_list):
        if self.env.context.get('_repack_material') is not _MATERIAL:
            raise UserError(_('Prepare los materiales desde el repaletizado.'))
        parents = self.env['step.packing.repack'].browse([vals['repack_id'] for vals in vals_list])
        parents._lock_material_repack()
        if any(p.state != 'draft' for p in parents):
            raise UserError(_('Los materiales validados no se modifican.'))
        return super().create(vals_list)

    def write(self, vals):
        self._check_editable()
        if vals.keys() - {'quantity'}:
            raise UserError(_('Solo puede ajustar el consumo del material calculado.'))
        return super().write(vals)

    def unlink(self):
        self._check_editable()
        if self.env.context.get('_repack_material') is not _MATERIAL:
            raise UserError(_('Recalcule los materiales desde el repaletizado.'))
        return super().unlink()


class RepackLine(models.Model):
    _inherit = 'step.packing.repack.line'

    @api.model_create_multi
    def create(self, vals_list):
        self.env['step.packing.repack'].browse([v['repack_id'] for v in vals_list if v.get('repack_id')])._lock_material_repack()
        return super().create(vals_list)

    def write(self, vals):
        self.repack_id._lock_material_repack()
        if 'repack_id' in vals and any(line.repack_id.id != vals['repack_id'] for line in self):
            raise UserError(_('La distribución conserva su repaletizado de origen.'))
        return super().write(vals)

    def unlink(self):
        self.repack_id._lock_material_repack()
        return super().unlink()
