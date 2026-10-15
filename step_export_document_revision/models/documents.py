"""Commercial documents reuse sales, contacts, packing OTs and native packages."""
import base64
import io

import xlsxwriter
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class Partner(models.Model):
    _inherit = 'res.partner'
    step_packing_csp = fields.Char(string='CSP', help='Código de la planta de packing.')


class Package(models.Model):
    _inherit = 'stock.quant.package'
    step_export_gross_kg = fields.Float(string='Gross Weight', digits='Stock Weight')
    step_export_thermos = fields.Char(string='Thermos')
    step_packing_date = fields.Date(related='step_packing_production_id.date', string='Date Packing')

    @api.constrains('step_export_gross_kg')
    def _check_export_gross(self):
        if any(p.step_export_gross_kg < 0 for p in self):
            raise ValidationError(_('El peso bruto no puede ser negativo.'))


class Order(models.Model):
    _inherit = 'sale.order'
    step_price_kg = fields.Boolean(string='Precio kg', default=False, tracking=True)
    step_box_pricing = fields.Boolean(string='Cálculo por cajas', default=False, copy=True,
        help='Las notas anteriores conservan sus cantidades hasta aplicar explícitamente el cálculo por cajas.')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if any(vals.get(k) for k in ('step_export_sale', 'step_export_shipment_id', 'step_export_sales_program_id')):
                vals.setdefault('step_box_pricing', True)
        return super().create(vals_list)

    def write(self, vals):
        if {'step_price_kg', 'step_box_pricing'} & vals.keys() and any(o.state not in ('draft', 'sent') for o in self):
            raise UserError(_('Cambie el criterio de precio únicamente en una nota sin confirmar.'))
        return super().write(vals)

    @api.constrains('step_price_kg', 'step_box_pricing')
    def _check_price_configuration(self):
        self.order_line._check_document_packaging()

    def action_apply_box_pricing(self):
        for order in self:
            if order.state not in ('draft', 'sent'):
                raise UserError(_('Aplique el cálculo en una nota sin confirmar.'))
            for line in order.order_line.filtered(lambda l: not l.display_type and l.step_export_charge == 'product'):
                line.product_uom_qty = line.step_export_boxes or line.product_uom_qty
                line.step_document_kg_per_box = line.product_packaging_id.step_export_kg_per_box
            order.step_box_pricing = True
        return True

    def action_print_export_proforma(self):
        self.ensure_one()
        return self.env.ref('step_sale_export_report.action_proforma').report_action(self)

    def action_print_export_invoice(self):
        self.ensure_one()
        return self.env.ref('step_export_document_revision.action_commercial_invoice').report_action(self)


class OrderLine(models.Model):
    _inherit = 'sale.order.line'
    step_document_kg = fields.Float(compute='_compute_document_kg', string='Kilos', digits=(16, 3))
    step_document_kg_per_box = fields.Float(string='Kg por caja acordados', digits=(16, 3), readonly=True,
        help='Peso del embalaje al seleccionarlo; conserva el precio acordado ante cambios posteriores del maestro.')

    @api.onchange('product_packaging_id')
    def _onchange_document_packaging(self):
        for line in self:
            line.step_document_kg_per_box = line.product_packaging_id.step_export_kg_per_box

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('product_packaging_id'):
                vals['step_document_kg_per_box'] = self.env['product.packaging'].browse(vals['product_packaging_id']).step_export_kg_per_box
        return super().create(vals_list)

    def write(self, vals):
        if 'product_packaging_id' in vals:
            vals = dict(vals, step_document_kg_per_box=self.env['product.packaging'].browse(vals['product_packaging_id']).step_export_kg_per_box if vals['product_packaging_id'] else 0)
        return super().write(vals)

    @api.depends('product_uom_qty', 'step_document_kg_per_box')
    def _compute_document_kg(self):
        for line in self:
            line.step_document_kg = line.product_uom_qty * line.step_document_kg_per_box

    def _prepare_base_line_for_taxes_computation(self, **kwargs):
        if self.order_id.step_box_pricing and self.order_id.step_price_kg and self.step_export_charge == 'product' and not self.display_type:
            kwargs.setdefault('quantity', self.step_document_kg)
        return super()._prepare_base_line_for_taxes_computation(**kwargs)

    @api.depends('product_uom_qty', 'discount', 'price_unit', 'tax_id', 'order_id.step_price_kg',
                 'order_id.step_box_pricing', 'step_document_kg_per_box', 'step_export_charge')
    def _compute_amount(self):
        return super()._compute_amount()

    def _prepare_invoice_line(self, **optional_values):
        vals = super()._prepare_invoice_line(**optional_values)
        if self.order_id.step_box_pricing and self.order_id.step_price_kg and self.step_export_charge == 'product' and not self.display_type:
            # Stock and invoice quantities remain product units/boxes. Convert
            # the price per kg to price per box for the standard invoice cycle.
            vals['price_unit'] = self.price_unit * self.step_document_kg_per_box
        return vals

    @api.constrains('product_packaging_id', 'product_id', 'product_uom_qty', 'order_id', 'step_export_charge', 'step_document_kg_per_box')
    def _check_document_packaging(self):
        for line in self:
            if line.order_id.step_box_pricing and not line.display_type and line.step_export_charge == 'product':
                package = line.product_packaging_id
                if not package or package.product_id != line.product_id or line.step_document_kg_per_box <= 0:
                    raise ValidationError(_('Seleccione un embalaje del producto con kilos por caja positivos.'))


class PackingList(models.Model):
    _inherit = 'step.export.packing.list'

    def _document_header(self):
        self.ensure_one()
        s = self.shipment_id
        return [('PRODUCT', s.species_id.display_name or ''), ('CNTR', self.container_number or ''),
                ('INVOICE', s.commercial_folio or ''), ('VESSEL', s.vessel_id.display_name or ''),
                ('ETD', str(s.departure_date or '')), ('ETA', str(s.arrival_date or '')), ('BK', s.booking or ''),
                ('EXPORTER', s.company_id.name), ('IMPORTER', (s.receiver_id or s.consignee_id).name or ''),
                ('POD', (s.destination_port_id.display_name or s.destination_port or '')),
                ('POL', (s.origin_port_id.display_name or s.origin_port or '')),
                ('TOTAL BOXES', self.box_qty), ('NET WEIGHT', sum(r[6] for r in self._document_rows()))]

    def _document_rows(self):
        self.ensure_one()
        rows = []
        for tag in self.tag_ids.sorted('name'):
            producers = tag.step_tag_line_ids.producer_id or tag.step_producer_id or tag.owner_id
            rows.append([tag.step_packing_partner_id.step_packing_csp or '', tag.name,
                tag.variedad_id.display_name or '', str(tag.step_packing_date or ''), ', '.join(sorted(set(producers.mapped('cod_csg')) - {False, ''})),
                tag.box_count, tag.step_actual_kg if tag.step_tag_line_ids else tag.kilos_total,
                tag.step_export_gross_kg, tag.step_export_thermos or '', tag.fruit_caliber_id.display_name or ''])
        return rows

    def _document_xlsx(self):
        self.ensure_one()
        stream = io.BytesIO()
        book = xlsxwriter.Workbook(stream, {'in_memory': True, 'strings_to_formulas': False, 'strings_to_urls': False})
        sheet = book.add_worksheet('Packing List')
        title = book.add_format({'bold': True, 'font_size': 20, 'align': 'center'})
        heading = book.add_format({'bold': True, 'border': 1, 'bg_color': '#E9EEF2'})
        cell = book.add_format({'border': 1})
        number = book.add_format({'border': 1, 'num_format': '#,##0.000'})
        sheet.set_landscape(); sheet.fit_to_pages(1, 0); sheet.set_paper(1)
        sheet.set_column('A:J', 17); sheet.set_column('B:B', 23)
        sheet.merge_range('A1:J3', 'PACKING LIST', title)
        if self.company_id.logo:
            sheet.insert_image('A1', 'logo.png', {'image_data': io.BytesIO(base64.b64decode(self.company_id.logo)),
                                                'x_scale': 0.15, 'y_scale': 0.15, 'object_position': 1})
        sheet.write('A5', 'Shipment', heading); sheet.write('B5', self.shipment_number or '', cell)
        sheet.write('F5', 'Dispatch guide', heading); sheet.write('G5', self.guide_id.external_folio or self.guide_id.name, cell)
        for index, (label, value) in enumerate(self._document_header()):
            row, col = (6 + index, 0) if index < 7 else (6 + index - 7, 5)
            sheet.write(row, col, label, heading); sheet.merge_range(row, col + 1, row, col + 3, value, cell)
        columns = ['CSP', 'FOLIO PALLET', 'VARIETY', 'DATE PACKING', 'CSG', 'BOXES', 'NET WEIGHT', 'GROSS WEIGHT', 'THERMOS', 'CALIBRE']
        sheet.write_row(15, 0, columns, heading)
        rows = self._document_rows()
        for ri, values in enumerate(rows, 16):
            for ci, value in enumerate(values):
                sheet.write(ri, ci, value, number if ci in (6, 7) else cell)
        end = 16 + len(rows)
        sheet.write(end, 4, 'TOTAL', heading)
        for col in (5, 6, 7): sheet.write_number(end, col, sum(r[col] for r in rows), number)
        sheet.autofilter(15, 0, max(15, end - 1), 9); sheet.freeze_panes(16, 2)
        sheet.print_area(0, 0, end, 9); sheet.repeat_rows(15)
        book.close()
        return stream.getvalue()

    def action_export_excel(self):
        self.ensure_one()
        self.check_access('read')
        attachment = self.env['ir.attachment'].create({'name': self.name.replace('/', '-') + '.xlsx',
            'datas': base64.b64encode(self._document_xlsx()), 'res_model': self._name, 'res_id': self.id,
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'})
        return {'type': 'ir.actions.act_url', 'url': '/web/content/%s?download=true' % attachment.id, 'target': 'self'}
