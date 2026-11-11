from collections import defaultdict
from datetime import date, datetime, time
from io import BytesIO
import base64
import math
import re
import unicodedata
from zipfile import ZipFile

import pytz
from openpyxl import load_workbook

from odoo import _, api, Command, fields, models
from odoo.addons.step_packing_reception_revision.models.simple_reception import ACTIVE_RECEPTION_TAG
from odoo.exceptions import UserError

from .reception_templates import RECEPTION_COLUMNS


_HEADER_ALIASES = {
    'folio': ('Folio Recep', 'Referencia', 'Folio recepción', 'Referencia de recepción'),
    'guide': ('N° Guía', 'Número de guía', 'Guía productor', 'Guía'),
    'tag': ('N° Lote', 'Número de tarja', 'N° Tarja', 'Tarja'),
    'date': ('Fecha/Hora Recep', 'Fecha prevista', 'Fecha recepción', 'Fecha de recepción'),
    'species': ('Especie',),
    'variety': ('Variedad', 'Fruta / Variedad'),
    'producer': ('Productor', 'Recibir de', 'Productor - Fundo', 'Productor o fundo'),
    'packaging': ('Envase', 'Embalaje'),
    'boxes': ('N° Cajas', 'Cantidad de embalajes', 'Cajas'),
    'kilos': ('KG Netos', 'Peso neto kg', 'Kilos netos'),
    'kind': ('Tipo Recep', 'Tipo de recepción de fruta'),
    'fruit_type': ('Concepto Fruta', 'Tipo de fruta'),
    'gassed': ('Fruta Gasificada',),
    'chilled': ('Fruta Con Frio',),
    'palletized': ('Fruta Palletizada',),
    'classification': ('Clasificación',),
}
_REQUIRED_COLUMNS = ('folio', 'guide', 'tag', 'date', 'species', 'variety', 'producer',
                     'packaging', 'boxes', 'kilos', 'fruit_type')
_DEFAULTS = ('picking_type_id', 'packing_id', 'season_id', 'product_id', 'category_id', 'fruit_class_id')
_COLUMN_LABELS = dict(RECEPTION_COLUMNS)
_SELECTIONS = {
    'fruit_type': {'convencional': 'conventional', 'organico': 'organic', 'organica': 'organic'},
    'gassed': {'s': 'yes', 'si': 'yes', 'n': 'no', 'no': 'no'},
    'classification': {'psj': 'psj', 'c&g': 'cg', 'gid': 'gid'},
}
_SELECTIONS['chilled'] = _SELECTIONS['palletized'] = _SELECTIONS['gassed']


def normalized(value):
    value = unicodedata.normalize('NFD', str(value or '').strip().casefold())
    return ' '.join(''.join(char for char in value if not unicodedata.combining(char)).split())


def header_key(value):
    return ' '.join(re.sub(r'[^a-z0-9]+', ' ', normalized(value)).split())


_HEADERS = {header_key(alias): column for column, aliases in _HEADER_ALIASES.items() for alias in aliases}


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
    elif isinstance(value, date):
        local = datetime.combine(value, time.min)
    else:
        text = ' '.join(str(value).split()).replace('/', '-')
        if re.match(r'^\d{4}-', text):
            local = datetime.fromisoformat(text)
        else:
            for pattern in ('%d-%m-%Y %H:%M', '%d-%m-%Y %H:%M:%S', '%d-%m-%Y'):
                try:
                    local = datetime.strptime(text, pattern)
                    break
                except ValueError:
                    continue
            else:
                raise ValueError('invalid reception date')
    timezone = pytz.timezone('America/Santiago')
    local = timezone.localize(local, is_dst=None) if local.tzinfo is None else local.astimezone(timezone)
    return local.date(), local.astimezone(pytz.UTC).replace(tzinfo=None)


def open_excel(file, filename):
    if not (filename or '').lower().endswith('.xlsx'):
        raise UserError(_('Cargue un archivo .xlsx.'))
    try:
        data = base64.b64decode(file)
        with ZipFile(BytesIO(data)) as archive:
            if len(data) > 5_000_000 or sum(item.file_size for item in archive.infolist()) > 50_000_000:
                raise ValueError('large workbook')
        return load_workbook(BytesIO(data), read_only=True, data_only=True, keep_links=False)
    except Exception as error:
        raise UserError(_('No se pudo leer el Excel. Verifique el formato y el tamaño del archivo.')) from error

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
    template_id = fields.Many2one('step.external.fruit.reception.template', string='Plantilla',
        check_company=True, domain="[('company_id', '=', company_id)]")
    template_name = fields.Char(string='Guardar como plantilla nueva')
    save_template = fields.Boolean(string='Guardar cambios en la plantilla', default=True)
    header_row = fields.Integer(string='Fila de encabezados', help='Deje 0 para detectarla automáticamente.')
    reviewed_row = fields.Integer(readonly=True)
    column_ids = fields.One2many('step.external.fruit.reception.column', 'wizard_id')
    alias_ids = fields.One2many('step.external.fruit.reception.alias', 'wizard_id')
    review_note = fields.Char(readonly=True)

    @api.onchange('template_id')
    def _onchange_template(self):
        if self.template_id:
            for field in _DEFAULTS:
                self[field] = self.template_id[field]
        self._clear_review()

    @api.onchange('file', 'header_row')
    def _clear_review(self):
        self.reviewed_row = 0
        self.column_ids = [Command.clear()]
        self.alias_ids = [Command.clear()]
        self.review_note = False


    @api.model
    def default_get(self, names):
        result = super().default_get(names)
        template = self.env['step.external.fruit.reception.template']._default_for_company()
        if template and 'template_id' in names and not result.get('template_id'):
            result['template_id'] = template.id
            for field in _DEFAULTS:
                if field in names and not result.get(field):
                    result[field] = template[field].id
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

    def _open_workbook(self):
        return open_excel(self.file, self.filename)

    def _suggest_columns(self, values):
        saved = self.template_id.columns or {}
        seen = defaultdict(int)
        columns = []
        for index, value in enumerate(values):
            source = reference(value)
            key = header_key(source)
            if not key:
                continue
            seen[key] += 1
            source_key = key if seen[key] == 1 else f'{key}#{seen[key]}'
            columns.append({'position': index, 'source': source, 'source_key': source_key,
                            'target': saved.get(source_key, _HEADERS.get(key, False))})
        return columns

    def _find_header(self, sheet):
        if not 0 <= self.header_row <= 100:
            raise UserError(_('Indique una fila de encabezados entre 1 y 100.'))
        best = (0, 0, [])
        for number, values in enumerate(sheet.iter_rows(max_row=self.header_row or 30, max_col=60, values_only=True), 1):
            columns = self._suggest_columns(values)
            if self.header_row == number:
                return number, columns
            score = len({line['target'] for line in columns if line['target'] in _REQUIRED_COLUMNS})
            if score > best[0]:
                best = (score, number, columns)
        if best[0] < 3:
            raise UserError(_('Indique el número de fila que contiene los encabezados del Excel.'))
        return best[1], best[2]

    def _column_positions(self, lines):
        columns = {}
        for line in lines:
            key = line['target']
            if not key:
                continue
            if key in columns:
                raise UserError(_('La columna «%s» tiene dos equivalencias. Elija una sola.', _COLUMN_LABELS[key]))
            columns[key] = line['position']
        missing = [_COLUMN_LABELS[key] for key in _REQUIRED_COLUMNS if key not in columns]
        if missing:
            raise UserError(_('Indique la columna del Excel para: %s.', ', '.join(missing)))
        return columns

    def _read_rows(self, rejected=None):
        book = self._open_workbook()
        try:
            sheet = book.worksheets[0]
            if self.reviewed_row:
                header = self.reviewed_row
                lines = self.column_ids.read(['position', 'target'])
            else:
                header, lines = self._find_header(sheet)
            columns = self._column_positions(lines)
            if sheet.max_row and sheet.max_row - header > 10000:
                raise UserError(_('Importe hasta 10.000 filas de detalle por archivo.'))
            rows = []
            for number, values in enumerate(sheet.iter_rows(min_row=header + 1,
                    max_row=min(sheet.max_row or header + 10000, header + 10000), max_col=60, values_only=True), header + 1):
                row = dict.fromkeys(_COLUMN_LABELS)
                row.update({key: values[index] for key, index in columns.items()})
                if not any(value is not None for value in values):
                    continue
                if not row['folio'] and any(normalized(value).startswith('>>totales') for value in values):
                    continue
                if normalized(row['kind']) == 'rechazado':
                    if rejected is not None:
                        rejected.append(reference(row['tag']))
                    continue
                rows.append((number, self._validate_row(row, number)))
        finally:
            book.close()
        if not rows:
            raise UserError(_('La primera hoja debe contener al menos una tarja aceptada para proceso.'))
        return rows

    def action_review(self):
        self.ensure_one()
        if not self.reviewed_row:
            book = self._open_workbook()
            try:
                header, columns = self._find_header(book.worksheets[0])
            finally:
                book.close()
            self.write({'reviewed_row': header, 'column_ids': [
                Command.clear(), *(Command.create(line) for line in columns)]})
        rejected = []
        try:
            rows = self._read_rows(rejected)
        except UserError as error:
            self.review_note = str(error)
        else:
            self._review_aliases(rows)
            folios = len({row['folio'] for _, row in rows})
            self.review_note = _('%(folios)s recepciones y %(tags)s tarjas aceptadas.',
                                 folios=folios, tags=len(rows))
            if rejected:
                tags = ', '.join(rejected[:10])
                self.review_note += _(' Se excluyen %(count)s tarjas rechazadas (%(tags)s).',
                                      count=len(rejected), tags=tags)
        action = self.env.ref('step_packing_ticket_revision.action_external_fruit_reception_import').read()[0]
        action.update(res_id=self.id, views=[(action['view_id'][0], 'form')])
        return action

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
        if row['kind'] and normalized(row['kind']) not in ('granel proceso', 'fruta a proceso'):
            raise UserError(_('Fila %s. El archivo debe contener fruta a proceso.', number))
        for key in ('folio', 'guide', 'tag'):
            row[key] = reference(row[key])
        for key, options in _SELECTIONS.items():
            value = normalized(row[key])
            if value and value not in options:
                raise UserError(_('Fila %(row)s. Valor no reconocido «%(value)s» en la columna %(field)s.',
                                  row=number, value=row[key], field=_COLUMN_LABELS[key]))
            row[key] = options.get(value, False)
        return dict(row, boxes=int(boxes), kilos=kilos, local=local, scheduled=scheduled)

    def _master_aliases(self, key):
        field = 'fundo_id' if key == 'producer' else 'packaging_id'
        saved = {line.source_key: line[field] for line in self.template_id.alias_ids
                 if line.kind == key and line[field]}
        saved.update({normalized(line.source): line[field] for line in self.alias_ids
                      if line.kind == key and line[field]})
        return saved

    def _review_aliases(self, rows):
        reviews = []
        for kind, masters, labels, field in self._equivalence_masters():
            saved = self._master_aliases(kind)
            for source in sorted({reference(row[kind]) for _, row in rows}, key=normalized):
                key = normalized(source)
                candidates = masters.filtered(lambda m: key in {normalized(label) for label in labels(m)})
                selected = saved.get(key)
                if (selected and selected in masters) or len(candidates) != 1:
                    reviews.append(Command.create({'kind': kind, 'source': source,
                                                    field: selected.id if selected and selected in masters else False}))
        self.alias_ids = [Command.clear(), *reviews]

    def _equivalence_masters(self):
        return (
            ('producer', self._masters('step.fundo', [('partner_id', '!=', False)]),
             lambda record: (record.name, record.partner_id.name), 'fundo_id'),
            ('packaging', self._masters('product.packaging', [('product_id', '=', self.product_id.id)]),
             lambda record: (record.name,), 'packaging_id'),
        )

    def _save_template(self):
        name = (self.template_name or '').strip()
        if not name and (not self.template_id or not self.save_template):
            return
        template = self.template_id if not name else self.env['step.external.fruit.reception.template']
        values = {field: self[field].id for field in _DEFAULTS}
        if template:
            self.env.cr.execute('SELECT id FROM step_external_fruit_reception_template WHERE id=%s FOR UPDATE',
                                [template.id])
            template.invalidate_recordset(['columns', 'alias_ids'])
        columns = dict(template.columns or {}) if template else {}
        columns.update({line.source_key: line.target or False for line in self.column_ids})
        values['columns'] = columns
        if template:
            template.write(values)
        else:
            template = template.create(dict(values, name=name, company_id=self.env.company.id))
        template._remember_aliases([
            {'source': line.source, 'source_key': normalized(line.source), 'kind': line.kind,
             'fundo_id': line.fundo_id.id, 'packaging_id': line.packaging_id.id}
            for line in self.alias_ids.filtered(lambda item: item.fundo_id or item.packaging_id)
        ])

    def _match(self, rows, key, masters, labels, fallback=None, saved=None):
        matches = {}
        unknown = {}
        for number, row in rows:
            source = normalized(row[key])
            if source in matches:
                continue
            preferred = (saved or {}).get(source)
            if preferred and preferred in masters:
                matches[source] = preferred
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
        resolved = {}
        for kind, masters, labels, field in self._equivalence_masters():
            resolved[kind] = self._match(rows, kind, masters, labels, self['fallback_' + field], self._master_aliases(kind))
        species = self._masters('step.especie')
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
            groups[row['folio']].append(dict(row, number=number, fundo=resolved['producer'][normalized(row['producer'])],
                                            especie=especie, variant=variant,
                                            container=resolved['packaging'][normalized(row['packaging'])]))
        # Match the native validation's lock so concurrent imports and manual
        # confirmations cannot claim the same tag number.
        for tag in sorted(seen_tags):
            self.env.cr.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))', ['steps-process-tag:' + tag])
        if (self.env['stock.quant.package'].sudo().search_count([
                ('name', 'in', list(seen_tags)), *ACTIVE_RECEPTION_TAG], limit=1)
                or self.env['step.packing.picking.tag.line'].sudo().search_count([
                    ('tag_number', 'in', list(seen_tags)), ('picking_id.state', '!=', 'cancel'),
                    ('picking_id.step_fruit_reversal_id', '=', False)], limit=1)):
            raise UserError(_('El archivo contiene un número de tarja ya utilizado o reservado por otra recepción.'))

        keys = {f'steps-receipt-folio:{company.id}:{self.packing_id.id}:{self.season_id.id}:{folio}' for folio in groups}
        keys.update(f'steps-receipt-guide:{company.id}:{lines[0]["guide"]}' for lines in groups.values())
        for key in sorted(keys):
            self.env.cr.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))', [key])
        pickings = self.env['stock.picking']
        with self.env.cr.savepoint():
            for folio, lines in groups.items():
                pickings |= self._create_reception(folio, lines, kg)
            self._save_template()
        action = self.env.ref('step_inventory_packing.action_steps_fruit_process_reception').read()[0]
        action.update(domain=[('id', 'in', pickings.ids)])
        if len(pickings) == 1:
            form = self.env.ref('step_packing_reception_revision.view_process_reception_form')
            action.update(res_id=pickings.id, views=[(form.id, 'form')])
        return action

    def _create_reception(self, folio, lines, kg):
        first = lines[0]
        header = ('guide', 'scheduled', 'especie', 'fundo', 'fruit_type', 'classification')
        if any(any(row[key] != first[key] for key in header) for row in lines[1:]):
            raise UserError(_('El folio %s tiene valores distintos en el encabezado. Corrija el archivo.', folio))
        company = self.env.company
        operation = self.picking_type_id
        source, destination = operation.default_location_src_id, operation.default_location_dest_id
        product = self.product_id
        model = self.env['stock.picking']
        active = [('company_id', '=', company.id), ('state', '!=', 'cancel'),
                  ('step_fruit_reversal_id', '=', False), ('step_fruit_reception_kind', '=', 'process')]
        if model.sudo().search_count([*active, '|', ('name', '=', folio),
                '&', ('step_external_reception_folio', '=', folio),
                '&', ('step_receiving_packing_id', '=', self.packing_id.id), ('fruit_season_id', '=', self.season_id.id)],
                limit=1):
            raise UserError(_('La referencia %s ya existe en las recepciones de Odoo.', folio))
        if model.sudo().search_count([
                *active,
                '|', ('fruit_fundo_id', '=', first['fundo'].id),
                '&', ('fruit_fundo_id', '=', False), ('partner_id', '=', first['fundo'].partner_id.id),
                ('fruit_guide_number', '=', first['guide']),
                ('step_receiving_packing_id', 'in', [False, self.packing_id.id])], limit=1):
            raise UserError(_('La guía %(guide)s ya tiene una recepción vigente para el fundo %(farm)s.',
                              guide=first['guide'], farm=first['fundo'].display_name))

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
                'step_fruit_gassed': row['gassed'], 'step_fruit_chilled': row['chilled'],
                'step_import_stock_quantity': kg._compute_quantity(row['kilos'], product.uom_id, round=False),
            }))
        moves = [{
            'name': product.display_name, 'product_id': product.id, 'product_uom': kg.id,
            'product_uom_qty': quantity, 'quantity': quantity, 'product_packaging_id': packaging.id,
            'location_id': source.id, 'location_dest_id': destination.id,
        } for packaging, quantity in quantities.items()]
        flags = {}
        for flag in ('gassed', 'chilled', 'palletized'):
            candidates = {row[flag] for row in lines}
            flags['step_fruit_' + flag] = next(iter(candidates)) if len(candidates) == 1 else False
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
            **flags,
            'step_fruit_reception_classification': first['classification'],
            'fruit_tag_line_ids': details,
        }
        if 'l10n_cl_delivery_guide_reason' in model._fields:
            values['l10n_cl_delivery_guide_reason'] = '6'
        receipt = model.create(values)
        # Creating the moves separately keeps Odoo from auto-confirming the draft.
        self.env['stock.move'].create([dict(move, picking_id=receipt.id, date=first['scheduled'])
                                       for move in moves])
        if product.tracking == 'lot':
            lots = self.env['stock.lot']
            for row in receipt.fruit_tag_line_ids:
                values = {'name': row.tag_number, 'product_id': product.id, 'company_id': company.id}
                lot = lots.search([(field, '=', value) for field, value in values.items()], limit=1)
                row.stock_lot_id = lot or lots.create(values)
        return receipt
