"""Explicit native warehouse sources and traceable movement of C tags to Packing."""
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

_TRANSFER = object()


class Company(models.Model):
    _inherit = 'res.company'

    step_packing_warehouse_id = fields.Many2one('stock.warehouse', string='Bodega Packing', check_company=True)
    step_packing_fruit_location_id = fields.Many2one('stock.location', string='Fruta a proceso en Packing', check_company=True)
    step_packing_material_location_id = fields.Many2one('stock.location', string='Origen de materiales Packing', check_company=True)

    @api.constrains('step_packing_warehouse_id', 'step_packing_fruit_location_id', 'step_packing_material_location_id')
    def _check_packing_locations(self):
        for company in self:
            warehouse = company.step_packing_warehouse_id
            locations = company.step_packing_fruit_location_id | company.step_packing_material_location_id
            if warehouse and warehouse.company_id != company:
                raise ValidationError(_('La bodega Packing debe pertenecer a la empresa.'))
            for location in locations:
                if (not warehouse or location.usage != 'internal' or location.company_id != company
                        or not location.parent_path.startswith(warehouse.view_location_id.parent_path)):
                    raise ValidationError(_('Las ubicaciones de Packing deben ser internas, de la misma empresa y estar dentro de su bodega Packing.'))

    def _configure_packing_warehouse(self):
        """Explicit deployment operation, never creates quants or stock moves."""
        self.ensure_one()
        self.check_access('write')
        self.env.cr.execute('SELECT id FROM res_company WHERE id=%s FOR UPDATE', [self.id])
        self.invalidate_recordset()
        if self.step_packing_warehouse_id:
            self._check_packing_locations()
            if not self.step_packing_fruit_location_id or not self.step_packing_material_location_id:
                raise ValidationError(_('Complete las dos ubicaciones de la bodega Packing configurada.'))
            return self.step_packing_warehouse_id
        warehouses = self.env['stock.warehouse'].with_context(active_test=False).search([
            ('company_id', '=', self.id), '|', ('name', '=ilike', 'Bodega Packing'), ('code', '=', 'BPCK')])
        if len(warehouses) > 1 or warehouses and not warehouses.active:
            raise ValidationError(_('Revise la bodega Packing existente: debe ser única y estar activa.'))
        warehouse = warehouses or self.env['stock.warehouse'].with_company(self).create({
            'name': 'Bodega Packing', 'code': 'BPCK', 'company_id': self.id})
        self.write({'step_packing_warehouse_id': warehouse.id,
                    'step_packing_fruit_location_id': warehouse.lot_stock_id.id,
                    'step_packing_material_location_id': warehouse.lot_stock_id.id})
        return warehouse


class Production(models.Model):
    _inherit = 'step.packing.production'

    step_packing_transfer_id = fields.Many2one(
        'stock.picking', string='Traslado de tarjas C a Packing', readonly=True, copy=False, check_company=True)
    step_stock_warehouse_id = fields.Many2one(related='company_id.step_packing_warehouse_id', string='Bodega Packing')
    step_stock_fruit_location_id = fields.Many2one(related='company_id.step_packing_fruit_location_id', string='Ubicación fruta a proceso')
    step_stock_material_location_id = fields.Many2one(related='company_id.step_packing_material_location_id', string='Origen materiales')

    def _stock_flow_configuration(self):
        self.ensure_one()
        company = self.company_id
        warehouse = company.step_packing_warehouse_id
        if not warehouse:
            return False
        company._check_packing_locations()
        if not warehouse.active or not company.step_packing_fruit_location_id or not company.step_packing_material_location_id:
            raise ValidationError(_('Complete la bodega y ubicaciones de Packing de la empresa.'))
        return warehouse

    def _transfer_fruit_to_packing(self):
        self.ensure_one()
        self._lock_process()
        warehouse = self._stock_flow_configuration()
        if not warehouse:
            return
        if self.state != 'validated':
            raise UserError(_('Valide la cuadratura antes del traslado a Packing.'))
        tags = self.step_packing_input_tag_ids
        source = self._packing_stock_location(tags)
        destination = self.company_id.step_packing_fruit_location_id
        if source == destination:
            return
        if self.step_packing_transfer_id:
            raise UserError(_('Las tarjas fueron movidas después de su traslado a Packing; revise sus movimientos.'))
        lines = [(quant.product_id, quant.quantity, tag, tag, quant.lot_id, quant.owner_id)
                 for tag in tags for quant in tag.quant_ids.filtered(lambda q: q.quantity > 0)]
        picking = self._create_packing_move(warehouse, source, destination, lines)
        self.with_context(_packing_stock_flow=_TRANSFER).write({'step_packing_transfer_id': picking.id})

    def action_step_packing_validate(self):
        with self.env.cr.savepoint():
            result = super().action_step_packing_validate()
            for record in self:
                record._transfer_fruit_to_packing()
            return result

    def action_step_packing_close(self):
        with self.env.cr.savepoint():
            for record in self:
                if record.state != 'validated':
                    raise UserError(_('Valide la OT antes de cerrarla.'))
                record._transfer_fruit_to_packing()
            return super().action_step_packing_close()

    def _consume_packaging_materials(self, warehouse, location, production_location):
        configured = self._stock_flow_configuration()
        if configured:
            warehouse, location = configured, self.company_id.step_packing_material_location_id
        return super()._consume_packaging_materials(warehouse, location, production_location)

    def _create_packing_move(self, warehouse, source, dest, lines):
        configured = self._stock_flow_configuration()
        return super()._create_packing_move(configured or warehouse, source, dest, lines)

    @api.model_create_multi
    def create(self, vals_list):
        if any(vals.get('step_packing_transfer_id') for vals in vals_list):
            raise UserError(_('El traslado a Packing se registra mediante la validación de la OT.'))
        return super().create(vals_list)

    def write(self, vals):
        if 'step_packing_transfer_id' in vals and self.env.context.get('_packing_stock_flow') is not _TRANSFER:
            raise UserError(_('El traslado a Packing se registra mediante la validación de la OT.'))
        return super().write(vals)
