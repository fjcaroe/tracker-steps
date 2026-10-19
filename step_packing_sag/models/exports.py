import base64
import io
import re
import math
import xlsxwriter
from odoo import fields, models, _
from odoo.exceptions import UserError


def numeric(value, width, label):
    """Anexo 5: letters become zero, left padding, never truncate identifiers."""
    value = str(value or '').strip()
    if not value or not re.fullmatch(r'[A-Za-z0-9]+', value):
        raise UserError(_('Complete %s con el código oficial sin separadores.') % label)
    value = re.sub(r'[A-Za-z]', '0', value)
    if len(value) > width or int(value) == 0:
        raise UserError(_('%s debe tener como máximo %s posiciones y no puede ser cero.') % (label, width))
    return value.zfill(width)


class SagExports(models.Model):
    _inherit = 'step.packing.inspection'
    sag_dispatch_sheet_reference = fields.Char('Nº planilla de despacho')
    sag_export_sequence = fields.Char('Correlativo Anexo 5', help='5 posiciones: SIF, recepción interplanta, repaletizaje, anulación o planilla, según el servicio.')
    sag_dispatch_date = fields.Date('Fecha de despacho', default=fields.Date.context_today)
    sag_repack_operation = fields.Selection([('A', 'Agregar'), ('M', 'Modificar'), ('E', 'Eliminar')], string='Operación de repaletizaje', default='M')
    sag_manual_dispatch = fields.Boolean('Planilla manual por indisponibilidad de Multipuerto')
    sag_product_condition = fields.Char('Condición del producto', help='Completar cuando corresponda. No exigida para productos frescos o de naturaleza seca, según §6.8.4.2.')

    def _sag_source_result(self, tag):
        self.ensure_one()
        records = self.search([('kind', '=', 'sag'), ('package_ids', 'in', tag.ids),
            ('sag_country_id', '=', self.sag_country_id.id)], order='id desc')
        result = records.filtered(lambda r: r._counts_for_dispatch())[:1]
        if not result or result.state != 'approved':
            raise UserError(_('La tarja %s necesita un resultado SAG aprobado para este destino.') % tag.name)
        return result

    def _sag_folio(self, tag):
        value = tag.step_sag_folio or tag.name
        if not tag.step_sag_folio and re.fullmatch(r'\d{1,10}-[0-9kK]', value or ''):
            value = value.rsplit('-', 1)[0]
        return numeric(value, 10, _('folio SAG de %s') % tag.name)

    def _sag_boxes(self, tag):
        boxes = tag.step_actual_boxes if tag.step_tag_line_ids else tag.box_count
        if boxes <= 0 or not float(boxes).is_integer():
            raise UserError(_('La tarja %s debe tener un número entero positivo de envases.') % tag.name)
        return int(boxes)

    def _sag_flat_file(self):
        self.ensure_one()
        self.check_access('read')
        fmt = self.sag_service_id.file_format
        if not fmt:
            raise UserError(_('El Anexo 5 adjunto no define un archivo para este servicio.'))
        if not self.package_ids or not self.sag_packing_id or not self.sag_country_id or not self.date:
            raise UserError(_('Complete establecimiento, país, fecha y tarjas.'))
        if fmt == 'INS' and any(tag.especie_id != self.sag_species_id for tag in self.package_ids):
            raise UserError(_('El archivo de inspección debe contener una sola especie.'))
        plant = numeric(self.sag_packing_id.step_sag_plant_number, 3, _('número de establecimiento sin región'))
        seq = numeric(self.sag_sif_reference if fmt == 'INS' else self.sag_export_sequence, 5, _('SIF / correlativo Anexo 5'))
        plant_header = plant.zfill(4)
        country = numeric(self.sag_country_id.step_sag_code, 3, _('código país SAG'))
        count = numeric(len(self.package_ids), 4, _('cantidad de pallets'))
        if fmt == 'INS':
            header = seq + plant_header + numeric(self.sag_species_id.sag_code, 8, _('código especie SAG')) + country + '000' + self.date.strftime('%Y%m%d') + count
        elif fmt in ('INT', 'DET'):
            header = seq + plant_header + count
        elif fmt == 'REP':
            header = plant_header + count
        else:
            if not self.sag_dispatch_date:
                raise UserError(_('Indique la fecha de despacho.'))
            header = plant_header + country + self.sag_dispatch_date.strftime('%Y%m%d') + count
        rows = []
        folios = set()
        for tag in self.package_ids.sorted('name'):
            folio = self._sag_folio(tag)
            if folio in folios:
                raise UserError(_('Dos tarjas se convierten al mismo folio SAG; revise sus identificadores.'))
            folios.add(folio)
            if fmt != 'INS':
                source = self._sag_source_result(tag)
            if fmt == 'DET':
                rows.append(folio)
                continue
            boxes = numeric(self._sag_boxes(tag), 4, _('envases de %s') % tag.name)
            species = numeric(tag.especie_id.sag_code, 8, _('código especie SAG'))
            if fmt == 'INS':
                rows.append(folio + boxes)
            elif fmt == 'DES':
                rows.append(folio + boxes + species)
            elif fmt == 'INT':
                rows.append(folio + boxes + species + country + source.date.strftime('%Y%m%d'))
            else:
                source_sif = numeric(source.sag_sif_reference, 5, _('SIF de origen de %s') % tag.name)
                if not self.sag_repack_operation:
                    raise UserError(_('Indique la operación de repaletizaje.'))
                row = self.sag_repack_operation + source_sif + folio
                if self.sag_repack_operation != 'E':
                    row += boxes + species + country + source.date.strftime('%Y%m%d')
                rows.append(row)
        return plant + seq + '.' + fmt, ('\r\n'.join([header, *rows, '&&', '', ''])).encode('ascii')

    def _sag_origins(self, tag):
        fundos = tag.fundo_id
        if not fundos:
            productions = self.env['step.packing.production'].search([('step_packing_output_tag_ids', 'in', tag.ids)])
            fundos = productions.fruit_fundo_id | productions.step_packing_input_tag_ids.fundo_id
        if not fundos:
            raise UserError(_('Relacione el fundo de origen de la tarja %s o de su OT.') % tag.name)
        cities = self.env['res.city']
        for fundo in fundos:
            city = fundo.step_sag_city_id or fundo.sector_id.city_id
            if not city or not city.step_sag_province_name:
                raise UserError(_('Complete comuna de origen y provincia en el fundo %s / maestro de comunas.') % fundo.name)
            cities |= city
        return ', '.join(sorted(set(cities.mapped('step_sag_province_name')))), ', '.join(sorted(cities.mapped('name')))

    def _sag_annex_rows(self):
        self.ensure_one()
        self.check_access('read')
        if not (self.sag_dispatch_sheet_reference or '').strip() or not self.package_ids:
            raise UserError(_('Indique el número de planilla de despacho y seleccione las tarjas.'))
        rows = []
        for tag in self.package_ids.sorted('name'):
            province, city = self._sag_origins(tag)
            source = self._sag_source_result(tag)
            rows.append([tag.name, tag.especie_id.name or '', tag.variedad_id.name or '', province, city,
                self._sag_boxes(tag), fields.Date.to_string(source.date), self.sag_country_id.name or '',
                ', '.join(sorted((tag.step_tag_line_ids.producer_id or tag.step_producer_id).mapped('name')))])
        return rows

    def _sag_annex_xlsx(self):
        self.ensure_one()
        rows = self._sag_annex_rows()
        stream = io.BytesIO()
        book = xlsxwriter.Workbook(stream, {'in_memory': True, 'strings_to_formulas': False, 'strings_to_urls': False})
        sheet = book.add_worksheet('Anexo despacho')
        title = book.add_format({'bold': True, 'font_size': 16})
        heading = book.add_format({'bold': True, 'bg_color': '#DDEBF7', 'border': 1, 'border_color': '#D9D9D9', 'text_wrap': True, 'valign': 'vcenter'})
        cell = book.add_format({'border': 1, 'border_color': '#D9D9D9', 'text_wrap': True, 'valign': 'vcenter'})
        number = book.add_format({'border': 1, 'border_color': '#D9D9D9', 'num_format': '#,##0', 'valign': 'vcenter'})
        sheet.set_landscape(); sheet.set_paper(9); sheet.fit_to_pages(1, 0)
        sheet.set_column('A:A', 22); sheet.set_column('B:E', 19); sheet.set_column('F:F', 12); sheet.set_column('G:I', 22)
        sheet.merge_range('A1:I1', 'ANEXO PLANILLA DE DESPACHO', title)
        sheet.merge_range('A2:I2', 'Planilla Nº ' + self.sag_dispatch_sheet_reference + ' · ' + self.company_id.name, heading)
        sheet.merge_range('A3:I3', 'País: ' + (self.sag_country_id.name or '') + ' · Condición: ' + (self.sag_product_condition or 'No indicada'), cell)
        sheet.write_row(3, 0, ['Folio pallet / bins', 'Especie', 'Variedades', 'Provincia de origen', 'Comuna de origen', 'Envases', 'Fecha inspección', 'Destino aprobado', 'Productores'], heading)
        sheet.set_row(3, 30); sheet.repeat_rows(0, 3); sheet.freeze_panes(4, 1)
        for index, row in enumerate(rows, 4):
            widths = [22, 19, 19, 19, 19, 12, 22, 22, 22]
            sheet.set_row(index, max(30, 14 * max(math.ceil(len(str(v)) / widths[c]) for c, v in enumerate(row)) + 8))
            for column, value in enumerate(row):
                sheet.write(index, column, value, number if column == 5 else cell)
        end = 4 + len(rows)
        sheet.write(end, 4, 'TOTAL ENVASES', heading)
        sheet.write_formula(end, 5, '=SUM(F5:F%s)' % end, number, sum(r[5] for r in rows))
        if self.sag_manual_dispatch:
            sheet.merge_range(end + 2, 0, end + 2, 8, 'Planilla emitida manualmente por problemas de conectividad', cell)
            sheet.merge_range(end + 3, 0, end + 3, 8, 'Contraparte: ' + (self.sag_counterpart_id.name or '') + '   Firma: ____________________', cell)
        sheet.merge_range(end + 5, 0, end + 5, 8, 'Anexo del establecimiento. La planilla oficial se emite / regulariza en Multipuerto.', cell)
        sheet.print_area(0, 0, end + 5, 8)
        book.close()
        return stream.getvalue()

    def _sag_download(self, name, data, mime):
        self.ensure_one()
        self.check_access('read')
        attachment = self.env['ir.attachment'].create({'name': name, 'datas': base64.b64encode(data),
            'mimetype': mime, 'res_model': self._name, 'res_id': self.id, 'public': False})
        return {'type': 'ir.actions.act_url', 'url': '/web/content/%s?download=true' % attachment.id, 'target': 'self'}

    def action_sag_flat_file(self):
        name, data = self._sag_flat_file()
        return self._sag_download(name, data, 'text/plain')

    def action_sag_annex_xlsx(self):
        return self._sag_download('Anexo_despacho_SAG_%s.xlsx' % self.id, self._sag_annex_xlsx(), 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

    def action_sag_annex_pdf(self):
        self._sag_annex_rows()
        return self.env.ref('step_packing_sag.report_dispatch_annex').report_action(self)


class SagAnnexReport(models.Model):
    _inherit = 'ir.actions.report'

    def _get_layout(self):
        # The annex has a complete inline print stylesheet. Keeping its layout
        # self-contained avoids HTTP asset requests while rendering in a clone,
        # a shell or a single-worker service; all other reports keep their layout.
        if len(self) == 1 and self.report_name == 'step_packing_sag.dispatch_annex':
            return self.env.ref('step_packing_sag.annex_minimal_layout')
        return super()._get_layout()
