from collections import defaultdict
from datetime import datetime
from io import BytesIO
import base64
import math
import unicodedata
from zipfile import ZipFile

import pytz
from openpyxl import load_workbook

from odoo import _, api, Command, fields, models
from odoo.exceptions import UserError


_HEADERS = {
    'folio recep': 'folio', 'n° guia': 'guide', 'n° lote': 'tag',
    'fecha/hora recep': 'date', 'especie': 'species', 'variedad': 'variety',
    'productor': 'producer', 'envase': 'packaging', 'n° cajas': 'boxes',
    'kg netos': 'kilos', 'tipo recep': 'kind', 'concepto fruta': 'fruit_type',
    'fruta gasificada': 'gassed', 'fruta con frio': 'chilled',
    'fruta palletizada': 'palletized', 'clasificacion': 'classification',
}
_SELECTIONS = {
    'fruit_type': {'convencional': 'conventional', 'organico': 'organic', 'organica': 'organic'},
    'gassed': {'s': 'yes', 'si': 'yes', 'n': 'no', 'no': 'no'},
    'classification': {'psj': 'psj', 'c&g': 'cg', 'gid': 'gid'},
}
_SELECTIONS['chilled'] = _SELECTIONS['palletized'] = _SELECTIONS['gassed']


def normalized(value):
    value = unicodedata.normalize('NFD', str(value or '').strip().casefold())
    return ' '.join(''.join(char for char in value if not unicodedata.combining(char)).split())


def reference(value):
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return str(value if value is not None else '').strip()


def excel_number(value):
    if isinstance(value, str):
        value = value.strip()
        if ',' in value:
            value = value.replace('.', '').replace(',', '.')
    number = float(value)
    if not math.isfinite(number):
        raise ValueError
    return number


def reception_date(value):
    if isinstance(value, datetime):
        local = value
    else:
        text = ' '.join(str(value).split()).replace('/', '-')
        try:
            local = datetime.strptime(text, '%d-%m-%Y %H:%M')
        except ValueError:
            local = datetime.strptime(text, '%d-%m-%Y %H:%M:%S')
    utc = pytz.timezone('America/Santiago').localize(local, is_dst=None).astimezone(pytz.UTC)
    return local.date(), utc.replace(tzinfo=None)


class ExternalReceptionImport(models.TransientModel):
    _name = 'step.external.fruit.reception.import'
    _description = 'Importar recepciones externas de fruta por Excel'
    _check_company_auto = True

    company_id = fields.Many2one('res.company', required=True, readonly=True, default=lambda self: self.env.company)
    picking_type_id = fields.Many2one('stock.picking.type', string='Operación de recepción',
        required=True, check_company=True, domain="[('code', '=', 'incoming'), ('company_id', '=', company_id)]")
    packing_id = fields.Many2one('res.partner', string='Packing', required=True, check_company=True,
        domain="[('step_export_packing', '=', True)]")
    season_id = fields.Many2one('step.temporada', string='Temporada', required=True)
    product_id = fields.Many2one('product.product', string='Producto', required=True, check_company=True)
    category_id = fields.Many2one('step.management.fruit.category', string='Categoría de fruta', required=True)
    fruit_class_id = fields.Many2one('step.management.fruit.class', string='Clase de fruta', required=True,
        domain="[('category_id', '=', category_id)]")
    fallback_fundo_id = fields.Many2one('step.fundo', string='Equivalencia de productor y fundo',
        help='Use este fundo cuando el archivo tenga un solo nombre de productor sin coincidencia única.')
    fallback_packaging_id = fields.Many2one('product.packaging', string='Equivalencia de embalaje', check_company=True,
        domain="[('product_id', '=', product_id)]",
        help='Use este embalaje cuando el archivo tenga un solo nombre de envase sin coincidencia única.')
    file = fields.Binary(string='Archivo Excel', required=True, attachment=False)
    filename = fields.Char(string='Nombre del archivo')

    @api.model
    def default_get(self, names):
        result = super().default_get(names)
        for field, model, domain in (
            ('season_id', 'step.temporada', [('name', '=ilike', 'T2627')]),
            ('product_id', 'product.product', [('default_code', '=', 'AR01')]),
            ('category_id', 'step.management.fruit.category', [('name', '=ilike', 'Materia Prima')]),
            ('fruit_class_id', 'step.management.fruit.class', [('name', '=ilike', 'A proceso')]),
        ):
            if field in names and not result.get(field):
                records = self._masters(model, domain)
                own = records.filtered(lambda row: 'company_id' in row._fields and row.company_id == self.env.company)
                records = own or records
                if len(records) == 1:
                    result[field] = records.id
        return result

    @api.model
    def _masters(self, model, domain=None):
        records = self.env[model]
        company = self.env.company
        return records.search(domain or []).filtered(lambda row: (
            company in row.company_ids if 'company_ids' in row._fields and row.company_ids
            else 'company_id' not in row._fields or not row.company_id or row.company_id in company.parent_ids | company
        ))

    def _read_rows(self):
        if not (self.filename or '').lower().endswith('.xlsx'):
            raise UserError(_('Cargue un archivo .xlsx.'))
        try:
            data = base64.b64decode(self.file)
            with ZipFile(BytesIO(data)) as archive:
                if len(data) > 5_000_000 or sum(item.file_size for item in archive.infolist()) > 50_000_000:
                    raise ValueError('large workbook')
            book = load_workbook(BytesIO(data), read_only=True, data_only=True, keep_links=False)
        except Exception as error:
            raise UserError(_('No se pudo leer el Excel. Verifique el formato y el tamaño del archivo.')) from error

        rows = []
        try:
            sheet = book.worksheets[0]
            if sheet.max_row and sheet.max_row > 10030:
                raise UserError(_('Importe hasta 10.000 filas de detalle por archivo.'))
            columns = {}
            for number, values in enumerate(sheet.iter_rows(max_row=min(sheet.max_row or 10031, 10031),
                                                            max_col=40, values_only=True), 1):
                if not columns:
                    headers = [normalized(value) for value in values]
                    if all(headers.count(name) == 1 for name in _HEADERS):
                        columns = {key: headers.index(name) for name, key in _HEADERS.items()}
                    elif number >= 30:
                        break
                    continue
                row = {key: values[index] for key, index in columns.items()}
                if not any(value is not None for value in values):
                    continue
                if not row['folio'] and normalized(row['packaging']) == '>>totales':
                    continue
                rows.append((number, self._validate_row(row, number)))
        finally:
            book.close()
        if not rows:
            raise UserError(_('La primera hoja debe contener los encabezados del archivo externo y al menos una tarja.'))
        return rows

    def _validate_row(self, row, number):
        required = ('folio', 'guide', 'tag', 'date', 'species', 'variety', 'producer', 'packaging', 'fruit_type')
        if any(not reference(row[key]) for key in required):
            raise UserError(_('Fila %s. Complete folio, guía, lote, fecha y datos de fruta y origen.', number))
        try:
            boxes, kilos = excel_number(row['boxes']), excel_number(row['kilos'])
            if boxes <= 0 or not boxes.is_integer() or kilos <= 0:
                raise ValueError
            local, scheduled = reception_date(row['date'])
        except (TypeError, ValueError, pytz.InvalidTimeError) as error:
            raise UserError(_('Fila %s. Revise la fecha, las cajas enteras y los kilos netos positivos.', number)) from error
        if normalized(row['kind']) not in ('granel proceso', 'fruta a proceso'):
            raise UserError(_('Fila %s. El archivo debe contener fruta a proceso.', number))
        for key in ('folio', 'guide', 'tag'):
            row[key] = reference(row[key])
        for key, options in _SELECTIONS.items():
            value = normalized(row[key])
            if value and value not in options:
                raise UserError(_('Fila %(row)s. Valor no reconocido «%(value)s» en la columna %(field)s.',
                                  row=number, value=row[key], field=next(label for label, k in _HEADERS.items() if k == key)))
            row[key] = options.get(value, False)
        return dict(row, boxes=int(boxes), kilos=kilos, local=local, scheduled=scheduled)

    def _match(self, rows, key, masters, labels, fallback=None):
        matches = {}
        unknown = {}
        for number, row in rows:
            source = normalized(row[key])
            if source in matches:
                continue
            candidates = masters.filtered(lambda master: source in {normalized(label) for label in labels(master)})
            if len(candidates) == 1:
                matches[source] = candidates
            else:
                unknown[source] = (number, row[key])
        if unknown:
            if len(unknown) == 1 and fallback and fallback in masters:
                matches[next(iter(unknown))] = fallback
            else:
                number, name = next(iter(unknown.values()))
                raise UserError(_('Fila %(row)s. «%(name)s» requiere una equivalencia única en el maestro %(model)s.',
                                  row=number, name=name, model=masters._description))
        return matches

    def action_import(self):
        self.ensure_one()
        company = self.env.company
        operation = self.picking_type_id
        source = operation.default_location_src_id
        destination = operation.default_location_dest_id
        if (self.company_id != company or operation.company_id != company or operation.code != 'incoming'
                or source.usage != 'supplier' or destination.usage != 'internal' or destination.company_id != company
                or not self.packing_id.step_export_packing or not company.step_fruit_inventory_enabled):
            raise UserError(_('Seleccione una operación de entrada de fruta, un packing y el stock de la empresa activa.'))
        kg = self.env.ref('uom.product_uom_kgm')
        product = self.product_id
        if not product.is_storable or product.tracking == 'serial' or product.uom_id.category_id != kg.category_id:
            raise UserError(_('Seleccione un producto almacenable por peso, sin seguimiento por número de serie.'))
        for master in (self.season_id, self.category_id, self.fruit_class_id):
            if master not in self._masters(master._name, [('id', '=', master.id)]):
                raise UserError(_('Seleccione temporada, categoría y clase habilitadas para esta empresa.'))
        if self.fruit_class_id.category_id != self.category_id:
            raise UserError(_('La clase de fruta debe pertenecer a la categoría seleccionada.'))

        rows = self._read_rows()
        fundos = self._masters('step.fundo', [('partner_id', '!=', False)])
        packaging = self._masters('product.packaging', [('product_id', '=', product.id)])
        species = self._masters('step.especie')
        farms = self._match(rows, 'producer', fundos, lambda m: (m.name, m.partner_id.name), self.fallback_fundo_id)
        containers = self._match(rows, 'packaging', packaging, lambda m: (m.name,), self.fallback_packaging_id)
        species_by_name = self._match(rows, 'species', species, lambda m: (m.name,))
        varieties = self._masters('step.variedad')
        groups = defaultdict(list)
        seen_tags = set()
        for number, row in rows:
            if row['tag'] in seen_tags:
                raise UserError(_('Fila %(row)s. La tarja %(tag)s está repetida en el archivo.', row=number, tag=row['tag']))
            seen_tags.add(row['tag'])
            especie = species_by_name[normalized(row['species'])]
            variant, = self._match([(number, row)], 'variety', varieties.filtered(
                lambda item: item.especie_id == especie), lambda m: (m.name,)).values()
            groups[row['folio']].append(dict(row, number=number, fundo=farms[normalized(row['producer'])],
                                            especie=especie, variant=variant,
                                            container=containers[normalized(row['packaging'])]))
        # Match the native validation's lock so concurrent imports and manual
        # confirmations cannot claim the same tag number.
        for tag in sorted(seen_tags):
            self.env.cr.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))', ['steps-process-tag:' + tag])
        if (self.env['stock.quant.package'].sudo().search_count([('name', 'in', list(seen_tags))], limit=1)
                or self.env['step.packing.picking.tag.line'].sudo().search_count([
                    ('tag_number', 'in', list(seen_tags)), ('picking_id.state', '!=', 'cancel')], limit=1)):
            raise UserError(_('El archivo contiene un número de tarja ya utilizado o reservado por otra recepción.'))

        pickings = self.env['stock.picking']
        with self.env.cr.savepoint():
            for folio, lines in groups.items():
                pickings |= self._create_reception(folio, lines, kg)
        action = self.env.ref('step_inventory_packing.action_steps_fruit_process_reception').read()[0]
        action.update(domain=[('id', 'in', pickings.ids)])
        if len(pickings) == 1:
            form = self.env.ref('step_packing_reception_revision.view_process_reception_form')
            action.update(res_id=pickings.id, views=[(form.id, 'form')])
        return action

    def _create_reception(self, folio, lines, kg):
        first = lines[0]
        header = ('guide', 'scheduled', 'especie', 'fundo', 'fruit_type', 'gassed', 'chilled', 'classification')
        if any(any(row[key] != first[key] for key in header) for row in lines[1:]):
            raise UserError(_('El folio %s tiene valores distintos en el encabezado. Corrija el archivo.', folio))
        company = self.env.company
        operation = self.picking_type_id
        source, destination = operation.default_location_src_id, operation.default_location_dest_id
        product = self.product_id
        model = self.env['stock.picking']
        if model.sudo().search_count([
                ('company_id', '=', company.id), ('state', '!=', 'cancel'),
                ('step_fruit_reception_kind', '=', 'process'),
                ('partner_id', '=', first['fundo'].partner_id.id),
                ('fruit_guide_number', '=', first['guide']),
                ('step_receiving_packing_id', 'in', [False, self.packing_id.id])], limit=1):
            raise UserError(_('El folio %s corresponde a una guía que ya tiene recepción.', folio))

        quantities = defaultdict(float)
        details = []
        for row in lines:
            packaging = row['container']
            quantities[packaging] += row['kilos']
            details.append(Command.create({
                'tag_number': row['tag'], 'product_id': product.id, 'variety_id': row['variant'].id,
                'packaging_id': packaging.id, 'category_id': self.category_id.id, 'uom_id': kg.id,
                'quantity': row['boxes'], 'box_count': row['boxes'], 'kilos': row['kilos'],
                'gross_kg': 0, 'tare_kg': 0, 'step_fruit_palletized': row['palletized'],
                'step_import_stock_quantity': kg._compute_quantity(row['kilos'], product.uom_id, round=False),
            }))
        moves = [Command.create({
            'name': product.display_name, 'product_id': product.id, 'product_uom': kg.id,
            'product_uom_qty': quantity, 'quantity': quantity, 'product_packaging_id': packaging.id,
            'location_id': source.id, 'location_dest_id': destination.id,
        }) for packaging, quantity in quantities.items()]
        palletized = {row['palletized'] for row in lines}
        values = {
            'picking_type_id': operation.id, 'company_id': company.id,
            'location_id': source.id, 'location_dest_id': destination.id,
            'partner_id': first['fundo'].partner_id.id, 'step_receiving_packing_id': self.packing_id.id,
            'step_fruit_reception_kind': 'process', 'step_external_reception_folio': folio,
            'scheduled_date': first['scheduled'], 'origin': first['guide'],
            'fruit_guide_number': first['guide'], 'fruit_harvest_date': first['local'],
            'step_fruit_guide_date': first['local'],
            'fruit_fundo_id': first['fundo'].id, 'fruit_species_id': first['especie'].id,
            'fruit_category_id': self.category_id.id, 'step_fruit_origin_class_id': self.fruit_class_id.id,
            'fruit_season_id': self.season_id.id, 'step_fruit_type': first['fruit_type'],
            'step_fruit_weighing_method': 'manual', 'step_fruit_weighing_by': 'unit',
            'step_fruit_gassed': first['gassed'], 'step_fruit_chilled': first['chilled'],
            'step_fruit_palletized': next(iter(palletized)) if len(palletized) == 1 else False,
            'step_fruit_reception_classification': first['classification'],
            'fruit_tag_line_ids': details, 'move_ids_without_package': moves,
        }
        if 'l10n_cl_delivery_guide_reason' in model._fields:
            values['l10n_cl_delivery_guide_reason'] = '6'
        receipt = model.create(values)
        if product.tracking == 'lot':
            lots = self.env['stock.lot']
            for row in receipt.fruit_tag_line_ids:
                values = {'name': row.tag_number, 'product_id': product.id, 'company_id': company.id}
                lot = lots.search([(field, '=', value) for field, value in values.items()], limit=1)
                row.stock_lot_id = lot or lots.create(values)
        return receipt
