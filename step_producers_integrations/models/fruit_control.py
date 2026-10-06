"""Read the original packing and export records by producer and fruit-tag line."""
from odoo import api, fields, models


class FruitPackage(models.Model):
    _inherit = 'stock.quant.package'

    step_producer_process_ids = fields.Many2many(
        'step.packing.production', relation='step_packing_output_tag_rel',
        column1='stock_quant_package_id', column2='step_packing_production_id',
        string='Núm. proceso', readonly=True)


class FruitLine(models.Model):
    _inherit = 'step.fruit.package.line'

    control_process_ids = fields.Many2many(related='package_id.step_producer_process_ids', compute_sudo=False)
    control_shipment_ids = fields.Many2many(related='package_id.step_export_shipment_ids', compute_sudo=False)
    control_species_id = fields.Many2one(related='package_id.especie_id', string='Especie')
    control_variety_id = fields.Many2one(related='package_id.variedad_id', string='Variedad')
    control_caliber_id = fields.Many2one(related='package_id.fruit_caliber_id', string='Calibre')
    control_category_id = fields.Many2one(related='package_id.fruit_category_id', string='Categoría')
    control_packaging_id = fields.Many2one(related='package_id.package_type_id', string='Embalaje / pallet')
    control_label = fields.Char(related='package_id.label', string='Etiqueta')
    control_tag_state = fields.Selection(related='package_id.step_tag_state', string='Estado tarja')
    control_tag_date = fields.Datetime(related='package_id.create_date', string='Fecha tarja')
    control_process_date = fields.Date(compute='_compute_control_dates', string='Fecha proceso')
    control_shipment_date = fields.Date(compute='_compute_control_dates', string='Fecha embarque')
    control_shipment_folio = fields.Char(compute='_compute_control_dates', string='Núm. embarque')
    control_pallet_qty = fields.Float(compute='_compute_pallet_qty', string='Pallets', digits=(16, 3))
    control_pending_kg = fields.Float(compute='_compute_pending_kg', string='Kg por exportar', digits='Stock Weight')
    control_settlement_ids = fields.Many2many(
        'step.export.producer.settlement', compute='_compute_control_fob', string='Núm. liquidación')
    control_fob_usd = fields.Float(compute='_compute_control_fob', string='FOB liquidado USD', digits=(16, 2))
    control_fob_unit_usd = fields.Float(compute='_compute_control_fob', string='FOB unit. liq. USD/kg', digits=(16, 4))

    @api.depends('control_process_ids.date', 'control_shipment_ids.departure_date',
                 'control_shipment_ids.date', 'control_shipment_ids.shipment_number')
    def _compute_control_dates(self):
        for line in self:
            dates = line.control_process_ids.mapped('date')
            line.control_process_date = min(dates) if dates else False
            dates = [shipment.departure_date or fields.Date.to_date(shipment.date)
                     for shipment in line.control_shipment_ids if shipment.departure_date or shipment.date]
            line.control_shipment_date = min(dates) if dates else False
            line.control_shipment_folio = ', '.join(line.control_shipment_ids.mapped('shipment_number'))

    @api.depends('kilos', 'package_id.step_actual_kg')
    def _compute_pallet_qty(self):
        for line in self:
            total = line.package_id.step_actual_kg
            line.control_pallet_qty = line.kilos / total if total else 0

    @api.depends('kilos', 'control_tag_state', 'package_id.step_tag_kind')
    def _compute_pending_kg(self):
        for line in self:
            line.control_pending_kg = line.kilos if (
                line.package_id.step_tag_kind == 'E' and line.control_tag_state == 'validated') else 0

    @api.depends('package_id', 'producer_id', 'kilos')
    def _compute_control_fob(self):
        # No sudo: the original settlement ACLs and company rules still apply.
        settlements = self.env['step.export.producer.settlement.line'].search([
            ('tag_id', 'in', self.mapped('package_id').ids),
            ('settlement_id.company_id', 'in', self.env.companies.ids),
            ('settlement_id.receiver_settlement_id', '!=', False),
            ('settlement_id.receiver_settlement_id.state', 'in', ['validated', 'accounted'])])
        for line in self:
            assigned = settlements.filtered(lambda row: row.tag_id == line.package_id
                                            and row.settlement_id.producer_id == line.producer_id)
            # Several product lines for one producer share its tag's allocation.
            producer_kg = sum(line.package_id.step_tag_line_ids.filtered(
                lambda row: row.producer_id == line.producer_id).mapped('kilos'))
            line.control_fob_unit_usd = sum(assigned.mapped('allocated_fob_usd')) / producer_kg if producer_kg else 0
            line.control_fob_usd = line.control_fob_unit_usd * line.kilos
            line.control_settlement_ids = assigned.mapped('settlement_id')

    def action_open_control_tag(self):
        self.ensure_one()
        return {'type': 'ir.actions.act_window', 'res_model': 'stock.quant.package',
                'res_id': self.package_id.id, 'view_mode': 'form'}
