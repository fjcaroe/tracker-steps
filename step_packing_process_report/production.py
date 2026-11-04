import base64
from collections import defaultdict
from datetime import date
from io import BytesIO

import xlsxwriter
from PIL import Image

from odoo import models
from odoo.tools import format_date, formatLang


RAW = ('Producto', 'Variedad', 'Lote', 'Embalaje', 'Cajas', 'Kilos')
INPUT = ('Folio pallet', 'Fecha', *RAW[1:])
FRUIT = ('Variedad', 'Productor', 'Embalaje', 'Calibre', 'Categoría', 'Cajas', 'Kilos')
BALANCE = ('Concepto', 'A Proceso', 'Exportación', 'Sobrepeso', 'Comercial',
           'Precalibre', 'Desecho', 'Merma')
CONCEPTS = ('input', 'export', 'overweight', 'commercial', 'precaliber', 'waste', 'loss')


def names(records):
    return ', '.join(dict.fromkeys(records.mapped('display_name')))


def group_rows(rows):
    totals = defaultdict(lambda: [0, 0])
    for *key, boxes, kilos in rows:
        total = totals[tuple(key)]
        total[0] += boxes
        total[1] += kilos
    return [key + tuple(total) for key, total in totals.items()]


def section(title, headers, rows, total=False):
    footer = ()
    if total:
        footer = ('Total', *([''] * (len(headers) - 3)),
                  sum(row[-2] for row in rows), sum(row[-1] for row in rows))
    return title, headers, rows, footer


class PackingProduction(models.Model):
    _inherit = 'step.packing.production'

    def _packing_report_data(self):
        self.ensure_one()
        self.check_access('read')
        header = [
            ('Número OT', self.name, 'Packing', self.packing_partner_id.display_name),
            ('Fecha proceso', self.date, 'Línea', self.step_packing_line_id.display_name),
            ('Número OP', self.step_packing_order_id.display_name, 'Productor', self.fruit_grower_id.display_name),
            ('Especie', self.fruit_species_id.display_name, 'Fundo', self.fruit_fundo_id.display_name),
            ('Variedad', self.fruit_variety_id.display_name, 'Pedido Venta', self.sale_order_id.display_name),
            ('Instructivo Embalaje', self.instruction_id.display_name, '', ''),
        ]
        raw, inputs = [], []
        packed, detail = {'E': [], 'N': []}, {'E': [], 'N': []}
        input_moves = self.input_picking_id.move_line_ids.grouped('package_id')
        for tag in self.step_packing_input_tag_ids:
            receipts = tag.step_reception_tag_line_ids.filtered(
                lambda line: line.picking_id.state != 'cancel')
            reception = receipts[:1].picking_id
            received = tag.received_at
            pallet_date = reception.step_fruit_guide_date or (received.date() if received else tag.harvest_date)
            lots = receipts.stock_lot_id | input_moves.get(tag, self.env['stock.move.line']).lot_id
            for line in tag.step_tag_line_ids:
                dims = (tag.variedad_id.display_name,
                        names(lots.filtered(lambda lot: lot.product_id == line.product_id)),
                        tag.step_packaging_id.display_name)
                raw.append((line.product_id.display_name, *dims, line.boxes, line.kilos))
                inputs.append((tag.name, pallet_date, *dims, line.boxes, line.kilos))
        for tag in self.step_packing_output_tag_ids:
            for line in tag.step_tag_line_ids:
                fruit = (tag.variedad_id.display_name, line.producer_id.display_name,
                         tag.step_packaging_id.display_name, tag.fruit_caliber_id.display_name,
                         tag.fruit_category_id.display_name, line.boxes, line.kilos)
                if tag.step_tag_kind in packed:
                    packed[tag.step_tag_kind].append((line.product_id.display_name, *fruit))
                detail['E' if tag.step_tag_kind == 'E' else 'N'].append((tag.name, *fruit))
        kg = tuple(self[f'step_packing_{key}_kg'] for key in CONCEPTS)
        percentages = tuple(value / kg[0] if kg[0] else 0.0 for value in kg)
        inspections = self.env['step.packing.inspection'].search([
            ('production_id', '=', self.id), ('kind', '=', 'internal'),
        ])
        return {
            'header': header,
            'left_header': True,
            'summary': [
                section('Materia prima', RAW, group_rows(raw)),
                section('Cuadratura', BALANCE, [('Kilos', *kg), ('% de kilos', *percentages)]),
                section('Fruta embalada (exportación)', ('Producto', *FRUIT), group_rows(packed['E']), total=True),
                section('Fruta embalada (nacional)', ('Producto', *FRUIT), group_rows(packed['N']), total=True),
            ],
            'detail': [
                section('Materia prima - folio pallet', INPUT, group_rows(inputs), total=True),
                section('Fruta exportación - folio pallet', ('Tarja', *FRUIT), group_rows(detail['E']), total=True),
                section('Fruta nacional - folio pallet', ('Tarja', *FRUIT), group_rows(detail['N']), total=True),
            ],
            'notes': [
                ('Folio Calidad', names(inspections)),
                ('Observaciones', '\n'.join(filter(None, inspections.mapped('observations')))),
            ],
        }

    def _packing_report_display(self, value, percentage=False):
        if isinstance(value, date):
            return format_date(self.env, value, date_format='dd/MM/yyyy')
        if isinstance(value, (float, int)) and not isinstance(value, bool):
            if percentage:
                return formatLang(self.env, value * 100, digits=2) + ' %'
            return formatLang(self.env, value, digits=2)
        return value or ''

    def _packing_process_xlsx(self):
        data = self._packing_report_data()
        stream = BytesIO()
        with xlsxwriter.Workbook(stream, {
            'in_memory': True, 'strings_to_formulas': False, 'strings_to_urls': False,
        }) as book:
            title = book.add_format({'bold': True, 'font_size': 16, 'align': 'center'})
            label = book.add_format({'bold': True, 'bg_color': '#E5EEE8', 'text_wrap': True})
            body = book.add_format({'text_wrap': True, 'valign': 'top'})
            total_text = book.add_format({'bold': True})
            total_number = book.add_format({'bold': True, 'num_format': '#,##0.00', 'align': 'right'})
            formats = {
                'date': book.add_format({'num_format': 'dd/mm/yyyy'}),
                'header_date': book.add_format({'num_format': 'dd/mm/yyyy', 'align': 'left'}),
                'number': book.add_format({'num_format': '#,##0.00'}),
                'percent': book.add_format({'num_format': '0.00%'}),
            }

            def write_value(sheet, row, col, value, percentage=False, bold=False):
                if isinstance(value, date):
                    sheet.write_datetime(row, col, value, formats['date'])
                elif isinstance(value, (float, int)) and not isinstance(value, bool):
                    style = total_number if bold else formats['percent' if percentage else 'number']
                    sheet.write_number(row, col, value, style)
                else:
                    sheet.write_string(row, col, value or '', total_text if bold else body)

            for tab, heading, sections in (
                ('OT packing', 'INFORME DE PROCESO PACKING', data['summary']),
                ('OT Anexo', 'INFORME DE PROCESO PACKING - DETALLE TARJAS', data['detail']),
            ):
                sheet = book.add_worksheet(tab)
                sheet.set_column('A:A', 29)
                sheet.set_column('B:F', 22)
                sheet.set_column('G:H', 15)
                sheet.set_landscape()
                sheet.set_paper(9)
                sheet.fit_to_pages(1, 0)
                logo = self.company_id.logo_web
                if logo:
                    image = BytesIO(base64.b64decode(logo))
                    with Image.open(image) as picture:
                        scale = min(150 / picture.width, 30 / picture.height, 1)
                    sheet.set_row(0, 26)
                    sheet.insert_image('A1', 'logo.png', {
                        'image_data': image, 'x_scale': scale, 'y_scale': scale,
                        'x_offset': 4, 'y_offset': 2,
                    })
                    sheet.merge_range('B1:H1', heading, title)
                else:
                    sheet.merge_range('A1:H1', heading, title)
                sheet.merge_range('A2:H2', self.company_id.name, label)
                for row, (left, first, right, second) in enumerate(data['header'], start=2):
                    sheet.write(row, 0, left, label)
                    if isinstance(first, date):
                        sheet.write_datetime(row, 1, first, formats['header_date'])
                    else:
                        sheet.merge_range(row, 1, row, 3, first or '', body)
                    sheet.write(row, 4, right, label)
                    sheet.merge_range(row, 5, row, 7, second or '', body)
                sheet.repeat_rows(0, 7)
                summary = tab == 'OT packing'
                row = 9
                for index, (caption, headers, rows, footer) in enumerate(sections):
                    sheet.merge_range(row, 0, row, 7, caption, label)
                    sheet.write_row(row + 1, 0, headers, label)
                    row += 2
                    for values in rows + ([footer] if footer else []):
                        for col, value in enumerate(values):
                            write_value(sheet, row, col, value, values[0] == '% de kilos',
                                        bold=summary and values is footer)
                        row += 1
                    row += 4 if summary and index < 2 else 2
                if summary:
                    for caption, value in data['notes']:
                        sheet.write(row, 0, caption, label)
                        sheet.merge_range(row, 1, row, 7, value or '', body)
                        sheet.set_row(row, min(400, 15 * max(1, value.count('\n') + 1)))
                        row += 1
        return stream.getvalue()

    def action_packing_process_xlsx(self):
        self.ensure_one()
        self.check_access('read')
        return {'type': 'ir.actions.act_url', 'target': 'download',
                'url': f'/packing/process/{self.id}/xlsx'}
