"""Client revision 2: one raw fruit, multiple outputs and destination reservations."""
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class PackingProduction(models.Model):
    _inherit = 'step.packing.production'

    raw_product_id = fields.Many2one('product.product', string='Materia prima')
    instruction_id = fields.Many2one('step.packing.instruction', string='Instructivo de embalaje')
    sales_program_id = fields.Many2one(related='step_packing_order_id.sales_program_id', string='Programa de ventas')
    sale_order_id = fields.Many2one('sale.order', string='Pedido de venta', check_company=True)

    @api.onchange('step_packing_input_tag_ids')
    def _onchange_input_fruit(self):
        for record in self:
            tag = record.step_packing_input_tag_ids[:1]
            if tag:
                record.raw_product_id = tag.step_tag_line_ids[:1].product_id
                record.fruit_grower_id = tag.step_producer_id
                record.fruit_fundo_id = tag.fundo_id
                record.fruit_species_id = tag.especie_id
                record.fruit_variety_id = tag.variedad_id

    def _check_packing_tags(self):
        result = super()._check_packing_tags()
        for record in self:
            products = record.step_packing_input_tag_ids.step_tag_line_ids.product_id
            if len(products) != 1 or record.raw_product_id and products != record.raw_product_id:
                raise ValidationError(_('La OT procesa una sola materia prima; revise las tarjas C.'))
            for tag in record.step_packing_output_tag_ids:
                if tag.step_packing_production_id and tag.step_packing_production_id != record:
                    raise ValidationError(_('Una tarja resultante pertenece a otra OT.'))
            if record.instruction_id and (record.instruction_id.order_id != record.step_packing_order_id or
                                          record.instruction_id.state != 'approved'):
                raise ValidationError(_('Use un instructivo aprobado de esta OP.'))
        return result

    def write(self, vals):
        protected = {'raw_product_id', 'instruction_id', 'sale_order_id', 'fruit_grower_id',
                     'fruit_fundo_id', 'fruit_species_id', 'fruit_variety_id'}
        if protected & vals.keys() and any(row.state != 'created' for row in self):
            raise UserError(_('La OT validada conserva la definición de su materia prima.'))
        return super().write(vals)

    def action_create_export_tag(self):
        return self._new_output_tag('E')

    def action_create_national_tag(self):
        return self._new_output_tag('N')

    def _new_output_tag(self, kind):
        self.ensure_one()
        if self.state != 'created':
            raise UserError(_('Cree las tarjas antes de validar la cuadratura.'))
        if not self.fruit_grower_id or not self.fruit_variety_id:
            raise UserError(_('Seleccione productor y variedad de la materia prima.'))
        return {'type': 'ir.actions.act_window', 'res_model': 'stock.quant.package',
                'view_mode': 'form', 'target': 'new', 'context': {
                    'default_is_fruit_tag': True, 'default_step_tag_kind': kind,
                    'default_step_tag_state': 'created', 'default_step_packing_production_id': self.id,
                    'default_step_packing_result': 'export' if kind == 'E' else 'commercial',
                    'default_step_producer_id': self.fruit_grower_id.id,
                    'default_fundo_id': self.fruit_fundo_id.id, 'default_especie_id': self.fruit_species_id.id,
                    'default_variedad_id': self.fruit_variety_id.id,
                    'default_fruit_type': self.step_packing_input_tag_ids[:1].fruit_type or 'conventional',
                    'default_ot_proceso': self.name, 'default_op_folio': self.step_packing_order_id.name}}


class FruitPackage(models.Model):
    _inherit = 'stock.quant.package'

    step_packing_production_id = fields.Many2one('step.packing.production', string='OT de Packing',
                                                ondelete='restrict', copy=False, index=True)
    step_packaging_id = fields.Many2one('product.packaging', string='Embalaje')
    step_result_product_id = fields.Many2one('product.product', compute='_compute_result_product', string='Producto')
    step_reserved_ids = fields.Many2many('step.export.stock.reservation', compute='_compute_reservations', string='Reservas vigentes')

    @api.depends('step_tag_line_ids.product_id')
    def _compute_result_product(self):
        for tag in self:
            tag.step_result_product_id = tag.step_tag_line_ids[:1].product_id

    def _compute_reservations(self):
        active = self.env['step.export.stock.reservation'].search([
            ('step_package_ids', 'in', self.ids), ('step_reservation_state', '=', 'reserved')])
        for tag in self:
            tag.step_reserved_ids = active.filtered(lambda reservation: tag in reservation.step_package_ids)

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for tag in records.filtered('step_packing_production_id'):
            ot = tag.step_packing_production_id
            ot._lock_process()
            if ot.state != 'created' or tag.step_tag_kind not in ('E', 'N') or tag.step_tag_state != 'created':
                raise ValidationError(_('Cree tarjas E/N para una OT abierta.'))
            ot.write({'step_packing_output_tag_ids': [(4, tag.id)]})
        return records

    def write(self, vals):
        if 'step_packing_production_id' in vals and any(tag.step_packing_production_id for tag in self):
            raise UserError(_('La tarja conserva su OT de origen.'))
        if {'step_tag_line_ids', 'step_packaging_id', 'step_packing_result'} & vals.keys():
            ots = self.step_packing_production_id
            ots._lock_process()
            if any(ot.state != 'created' or ot.material_review_state == 'approved' for ot in ots):
                raise UserError(_('Reabra cuadratura y materiales antes de cambiar una tarja de salida.'))
        return super().write(vals)


class PackingStockReservation(models.Model):
    _inherit = 'step.export.stock.reservation'

    destination_country_id = fields.Many2one('res.country', string='Mercado / país')
    sales_program_id = fields.Many2one('step.export.sales.program', string='Programa de ventas', check_company=True)
    species_id = fields.Many2one('step.especie', string='Filtrar especie')
    variety_id = fields.Many2one('step.variedad', string='Filtrar variedad')
    producer_id = fields.Many2one('res.partner', string='Filtrar productor')
    caliber_id = fields.Many2one('step.management.fruit.caliber', string='Filtrar calibre')
    category_id = fields.Many2one('step.management.fruit.category', string='Filtrar categoría')
    tag_kind = fields.Selection([('C', 'Cosecha'), ('E', 'Exportación'), ('N', 'Nacional')], string='Filtrar tipo')
    boxes_total = fields.Float(compute='_compute_totals', string='Cajas')
    kilos_total = fields.Float(compute='_compute_totals', string='Kilos')

    @api.depends('step_package_ids.step_tag_line_ids.boxes', 'step_package_ids.step_tag_line_ids.kilos')
    def _compute_totals(self):
        for record in self:
            record.boxes_total = sum(record.step_package_ids.step_tag_line_ids.mapped('boxes'))
            record.kilos_total = sum(record.step_package_ids.mapped('step_actual_kg'))

    def write(self, vals):
        if {'destination_country_id', 'sales_program_id'} & vals.keys() and any(
                row.step_reservation_state != 'draft' for row in self):
            raise UserError(_('Libere la reserva antes de cambiar su destino.'))
        return super().write(vals)


class Shipment(models.Model):
    _inherit = 'step.export.export'

    def _check_reserved_destination(self):
        for shipment in self:
            reservations = self.env['step.export.stock.reservation'].search([
                ('step_package_ids', 'in', shipment.tag_ids.ids), ('step_reservation_state', '=', 'reserved')])
            for reservation in reservations:
                if reservation.company_id != shipment.company_id or (
                        reservation.sales_program_id and reservation.sales_program_id != shipment.sales_program_id) or (
                        reservation.destination_country_id and reservation.destination_country_id != shipment.destination_country_id):
                    raise ValidationError(_('Una tarja está reservada para otro mercado o programa. Libere la reserva o use su destino autorizado.'))

    @api.constrains('tag_ids', 'sales_program_id', 'destination_country_id', 'company_id')
    def _check_reservations_on_assignment(self):
        self._check_reserved_destination()

    def _check_tag_load(self):
        self._check_reserved_destination()
        return super()._check_tag_load()

    def action_validate_shipment(self):
        self._check_reserved_destination()
        return super().action_validate_shipment()


class Repack(models.Model):
    _inherit = 'step.packing.repack'

    date = fields.Date(string='Fecha proceso', default=fields.Date.context_today, required=True)
    process_type_id = fields.Many2one('step.packing.process.type', string='Tipo de proceso', domain="[('step_category','=','correction')]")
    packing_partner_id = fields.Many2one('res.partner', string='Packing')
    packing_line_id = fields.Many2one('step.packing.line', string='Línea')
    source_tag_ids = fields.Many2many('stock.quant.package', compute='_compute_tags', string='Tarjas que salen')
    target_tag_ids = fields.Many2many('stock.quant.package', compute='_compute_tags', string='Tarjas que entran')

    @api.depends('line_ids.source_package_id', 'line_ids.target_package_id')
    def _compute_tags(self):
        for record in self:
            record.source_tag_ids = record.line_ids.source_package_id
            record.target_tag_ids = record.line_ids.target_package_id

    def _check_repack(self):
        if self.process_type_id and self.process_type_id.step_category != 'correction':
            raise ValidationError(_('El repaletizado pertenece a la categoría Corrección.'))
        return super()._check_repack()

    def write(self, vals):
        if {'date', 'process_type_id', 'packing_partner_id', 'packing_line_id'} & vals.keys() and any(row.state == 'done' for row in self):
            raise UserError(_('El repaletizado validado conserva sus datos de proceso.'))
        return super().write(vals)


class PackageLine(models.Model):
    _inherit = 'step.fruit.package.line'
    source_package_id = fields.Many2one('stock.quant.package', string='Tarja de origen', ondelete='restrict', copy=False)

    def _check_open_ot(self):
        ots = self.package_id.step_packing_production_id
        ots._lock_process()
        if any(ot.state != 'created' or ot.material_review_state == 'approved' for ot in ots):
            raise UserError(_('Reabra cuadratura y materiales antes de cambiar el detalle de salida.'))

    @api.model_create_multi
    def create(self, vals_list):
        packages = self.env['stock.quant.package'].browse([row['package_id'] for row in vals_list if row.get('package_id')])
        packages.step_tag_line_ids._check_open_ot()
        ots = packages.step_packing_production_id
        ots._lock_process()
        if any(ot.state != 'created' or ot.material_review_state == 'approved' for ot in ots):
            raise UserError(_('No agregue detalle a una OT validada o con materiales aprobados.'))
        return super().create(vals_list)

    def write(self, vals):
        self._check_open_ot()
        if 'package_id' in vals:
            raise UserError(_('El detalle conserva su tarja.'))
        return super().write(vals)

    def unlink(self):
        self._check_open_ot()
        return super().unlink()
