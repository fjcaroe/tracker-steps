import base64
from datetime import date, datetime, time, timedelta
from io import BytesIO

import pytz
import xlsxwriter
from PIL import Image

from odoo import Command, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.osv.expression import AND, OR
from odoo.tools import email_normalize, html2plaintext


def label(records):
    return ', '.join(dict.fromkeys(records.mapped('display_name')))


def total_row(rows, width, numeric_columns, ratio=None):
    result = [''] * width
    result[0] = 'Total'
    for index in numeric_columns:
        result[index] = sum(row[index] for row in rows)
    if ratio:
        target, numerator, denominator = ratio
        result[target] = result[numerator] / result[denominator] if result[denominator] else 0
    return tuple(result)


class DocumentMixin(models.AbstractModel):
    _name = 'step.packing.document.mixin'
    _description = 'Salida de documentos de Packing'

    def _packing_report_display(self, value, percentage=False):
        return self.env['step.packing.production']._packing_report_display(value, percentage)

    def _document_xlsx(self):
        document = self._document_data()
        stream = BytesIO()
        with xlsxwriter.Workbook(stream, {
            'in_memory': True, 'strings_to_formulas': False, 'strings_to_urls': False,
        }) as book:
            sheet = book.add_worksheet('Packing')
            sheet.set_landscape()
            sheet.set_paper(9)
            sheet.fit_to_pages(1, 0)
            width = max(len(section[1]) for section in document['sections'])
            sheet.set_column(0, width - 1, 18)
            sheet.set_column(0, 0, 28)
            heading = book.add_format({'bold': True, 'font_size': 16})
            header = book.add_format({'bold': True, 'bg_color': '#E5EEE8', 'text_wrap': True})
            body = book.add_format({'text_wrap': True})
            numeric = book.add_format({'num_format': '#,##0.00'})
            percent = book.add_format({'num_format': '0.00%'})
            calendar = book.add_format({'num_format': 'dd/mm/yyyy'})
            logo = self.company_id.logo_web
            first_column = 0
            if logo:
                image = BytesIO(base64.b64decode(logo))
                with Image.open(image) as picture:
                    scale = min(145 / picture.width, 30 / picture.height, 1)
                sheet.set_row(0, 25)
                sheet.insert_image(0, 0, 'logo.png', {
                    'image_data': image, 'x_scale': scale, 'y_scale': scale,
                })
                first_column = 1
            sheet.merge_range(0, first_column, 0, width - 1, document['title'], heading)
            sheet.merge_range(1, 0, 1, width - 1, self.company_id.name, header)
            row = 3
            for left, value, right, second in document['header']:
                sheet.write(row, 0, left, header)
                if isinstance(value, date):
                    sheet.write_datetime(row, 1, value, calendar)
                else:
                    sheet.merge_range(row, 1, row, 2, value or '', body)
                sheet.write(row, 3, right, header)
                sheet.merge_range(row, 4, row, width - 1, second or '', body)
                row += 1
            row += 1
            for caption, columns, rows, footer in document['sections']:
                sheet.merge_range(row, 0, row, width - 1, caption, header)
                sheet.write_row(row + 1, 0, columns, header)
                row += 2
                for values in rows + ([footer] if footer else []):
                    for index, value in enumerate(values):
                        if isinstance(value, date):
                            sheet.write_datetime(row, index, value, calendar)
                        elif isinstance(value, (float, int)) and not isinstance(value, bool):
                            style = percent if columns[index].startswith('%') else numeric
                            sheet.write_number(row, index, value, style)
                        else:
                            sheet.write_string(row, index, value or '', body)
                    row += 1
                row += 2
        return stream.getvalue()

    def _document_attachment(self, extension, content):
        return self.env['ir.attachment'].create({
            'name': f"{self._document_data()['title']}.{extension}",
            'datas': base64.b64encode(content),
            'mimetype': 'application/pdf' if extension == 'pdf' else
                        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'res_model': self._name, 'res_id': self.id,
        })

    def action_document_xlsx(self):
        attachment = self._document_attachment('xlsx', self._document_xlsx())
        return {'type': 'ir.actions.act_url', 'target': 'download',
                'url': f'/web/content/{attachment.id}?download=true'}


class PackingOrder(models.Model):
    _name = 'step.packing.order'
    _inherit = ['step.packing.order', 'step.packing.document.mixin']

    def _document_data(self):
        self.ensure_one()
        self.check_access('read')
        lines = self.line_ids
        instructions = self.instruction_ids.filtered(lambda row: row.state == 'approved')
        rows = [(line.product_id.display_name, line.variety_id.display_name, line.packaging_id.display_name,
                 line.bom_id.display_name, line.caliber_id.display_name, line.boxes, line.kilos) for line in lines]
        materials = [(need.product_id.display_name, need.uom_id.display_name,
                      need.required_qty, need.available_qty, need.shortage_qty) for need in self.material_need_ids]
        return {
            'title': 'ORDEN DE PROCESO PACKING',
            'header': [
                ('Número OP', self.name, 'Packing', self.packing_partner_id.display_name),
                ('Fecha OP', self.week_start, 'Programa de venta', self.sales_program_id.display_name),
                ('Especie', label(lines.species_id), 'Instructivo Embalaje',
                 label(instructions) or html2plaintext(self.instruction or '')),
                ('Variedad', label(lines.variety_id), 'Pedido Venta', label(self.production_ids.sale_order_id)),
            ],
            'sections': [
                ('Productos a embalar', ('Producto', 'Variedad', 'Embalaje', 'Lista de materiales',
                 'Calibres', 'Cajas', 'Kilos'), rows, total_row(rows, 7, (5, 6))),
                ('Materiales', ('Producto', 'U Medida', 'Cantidad', 'Disponible', 'Faltante'), materials, ()),
            ],
        }


class ProducerDocument(models.TransientModel):
    _name = 'step.packing.producer.document'
    _inherit = 'step.packing.document.mixin'
    _description = 'Informe de Packing para productor'

    kind = fields.Selection([('reception', 'Recepciones'), ('process', 'Proceso')], required=True)
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    producer_id = fields.Many2one('res.partner', string='Productor', required=True)
    date_from = fields.Date(string='Desde', required=True)
    date_to = fields.Date(string='Hasta', required=True, default=fields.Date.context_today)

    @api.constrains('date_from', 'date_to')
    def _check_period(self):
        for record in self:
            if record.date_from > record.date_to:
                raise ValidationError('La fecha final debe ser igual o posterior a la inicial.')

    def _document_data(self):
        self.ensure_one()
        self.check_access('read')
        self._check_period()
        if self.company_id not in self.env.companies:
            raise UserError('Seleccione una compañía activa.')
        if self.kind == 'reception':
            title, fund, species, weeks, section = self._reception_data()
        else:
            title, fund, species, weeks, section = self._process_data()
        return {
            'title': title,
            'header': [
                ('Productor', self.producer_id.display_name, 'Fundo productor', fund),
                ('Dirección', self.producer_id.contact_address, 'Periodo',
                 f'{self.date_from:%d/%m/%Y} al {self.date_to:%d/%m/%Y}'),
                ('Número semana', weeks, 'Especie', species),
                ('Responsable', self.env.user.display_name, '', ''),
            ],
            'sections': [section],
        }

    def _weeks(self):
        monday = self.date_from - timedelta(days=self.date_from.weekday())
        weeks = [(monday + timedelta(weeks=offset)).isocalendar()[:2]
                 for offset in range((self.date_to - monday).days // 7 + 1)]
        return ', '.join(f'{year}-S{week:02}' for year, week in weeks)

    def _receipt_day(self, receipt):
        if receipt.date_done:
            return fields.Datetime.context_timestamp(self, receipt.date_done).date()
        return receipt.step_fruit_guide_date

    def _reception_data(self):
        zone = pytz.timezone(self.env.context.get('tz') or self.env.user.tz or 'UTC')
        start = zone.localize(datetime.combine(self.date_from, time.min)).astimezone(pytz.UTC).replace(tzinfo=None)
        end = zone.localize(datetime.combine(self.date_to + timedelta(days=1), time.min)).astimezone(pytz.UTC).replace(tzinfo=None)
        domain = AND([[
            ('company_id', '=', self.company_id.id), ('state', '=', 'done'),
            ('step_fruit_reception_kind', 'in', ['process', 'packed']),
            ('fruit_fundo_id.partner_id', '=', self.producer_id.id),
        ], OR([
            [('date_done', '>=', start), ('date_done', '<', end)],
            [('date_done', '=', False), ('step_fruit_guide_date', '>=', self.date_from),
             ('step_fruit_guide_date', '<=', self.date_to)],
        ])])
        receipts = self.env['stock.picking'].search(domain)
        rows = []
        for receipt in receipts.sorted(lambda row: (self._receipt_day(row), row.id)):
            for pallet in receipt.fruit_tag_line_ids:
                boxes, net = pallet.quantity, pallet.kilos
                rows.append((self._receipt_day(receipt), receipt.fruit_guide_number or '',
                             pallet.package_id.name or pallet.tag_number or '', pallet.variety_id.display_name,
                             pallet.packaging_id.display_name, boxes, pallet.gross_kg, net, net / boxes if boxes else 0))
        headers = ('Fecha recepción', 'Guía', 'Folio tarja', 'Variedad', 'Embalaje',
                   'Cantidad envases', 'Kilos brutos', 'Kilos netos', 'Promedio caja')
        section = ('Recepciones', headers, rows, total_row(rows, 9, (5, 6, 7), (8, 7, 5)))
        return ('INFORME DE RECEPCIONES', label(receipts.fruit_fundo_id), label(receipts.fruit_species_id),
                self._weeks(), section)

    def _process_data(self):
        orders = self.env['step.packing.production'].search([
            ('company_id', '=', self.company_id.id), ('fruit_grower_id', '=', self.producer_id.id),
            ('date', '>=', self.date_from), ('date', '<=', self.date_to),
            ('state', 'in', ['validated', 'closed', 'costed', 'accounted']),
        ], order='date, id')
        rows = []
        for order in orders:
            raw = order.step_packing_input_tag_ids
            tags = raw | order.step_packing_output_tag_ids
            if tags.step_tag_line_ids.producer_id - self.producer_id:
                raise UserError('La OT %s contiene fruta de varios productores y requiere una separación antes de emitir el informe.' % order.name)
            output = order.step_packing_output_tag_ids.filtered(lambda tag: tag.step_tag_kind == 'E')
            receptions = raw.step_reception_tag_line_ids.filtered(lambda line: line.picking_id.state == 'done')
            input_kg = order.step_packing_input_kg
            export_kg = order.step_packing_export_kg
            dates = sorted({day for receipt in receptions.picking_id if (day := self._receipt_day(receipt))})
            lots = receptions.stock_lot_id | order.input_picking_id.move_line_ids.lot_id
            rows.append((', '.join(day.strftime('%d/%m/%Y') for day in dates), label(lots), order.name,
                         ', '.join(raw.mapped('name')), label(raw.variedad_id) or order.fruit_variety_id.display_name,
                         input_kg, label(output.step_packaging_id), sum(output.mapped('step_actual_boxes')),
                         export_kg, order.step_packing_overweight_kg, order.step_packing_commercial_kg,
                         order.step_packing_loss_kg, export_kg / input_kg if input_kg else 0))
        headers = ('Fecha recepción', 'Lote', 'OT Packing', 'Folios tarjas', 'Variedad', 'Kilos a proceso',
                   'Embalaje', 'Cajas terminadas', 'Kg exportación', 'Sobrepeso', 'Comercial IQF', 'Merma', '% exportación')
        section = ('Procesos', headers, rows, total_row(rows, 13, (5, 7, 8, 9, 10, 11), (12, 8, 5)))
        return ('INFORME DE PROCESO', label(orders.fruit_fundo_id), label(orders.fruit_species_id),
                self._weeks(), section)

    def action_document_pdf(self):
        self._document_data()
        return self.env.ref('step_packing_producer_documents.action_producer_pdf').report_action(self, config=False)

    def action_document_email(self):
        document = self._document_data()
        address = email_normalize(self.producer_id.email or '')
        if not address:
            raise UserError('El productor debe tener un correo válido registrado.')
        if not document['sections'][0][2]:
            raise UserError('El periodo seleccionado no contiene datos para enviar.')
        action = self.env.ref('step_packing_producer_documents.action_producer_pdf')
        pdf, kind = self.env['ir.actions.report']._render_qweb_pdf(action.report_name, self.ids)
        if kind != 'pdf' or not pdf.startswith(b'%PDF'):
            raise UserError('No se pudo generar el PDF del informe.')
        attachments = self._document_attachment('pdf', pdf) | self._document_attachment('xlsx', self._document_xlsx())
        self.env['mail.mail'].sudo().create({
            'email_to': address,
            'subject': document['title'],
            'body_html': '<p>Adjuntamos el informe de Packing del periodo seleccionado en PDF y Excel.</p>',
            'attachment_ids': [Command.set(attachments.ids)],
            'auto_delete': True,
        })
        return {
            'type': 'ir.actions.client', 'tag': 'display_notification',
            'params': {'title': 'Informe en cola de correo', 'type': 'success'},
        }
