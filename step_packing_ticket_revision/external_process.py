from collections import defaultdict
from datetime import date, datetime

from odoo import _, api, Command, fields, models
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_compare

from .external_reception import _SELECTIONS, excel_number, header_key, normalized, open_excel, reference


_COMMERCIAL = 'fruta iqf mermas bajo calibre'
_YIELD = 'rendimiento'
_OVERWEIGHT = {'excedente de fruta por deshidratacion', 'sobre peso'}
_SECTIONS = {
    'fruta procesada': {
        'n op': 'folio', 'n guia': 'guide', 'n lote': 'tag', 'linea op': 'line',
        'productor': 'producer', 'especie': 'species', 'variedad': 'variety',
        'concepto fruta': 'fruit_type', 'kilos': 'kilos', 'cant bandejas': 'boxes',
    },
    'fruta embalada': {
        'n op': 'folio', 'folio pallet': 'tag', 'f embalaje': 'date', 'linea': 'line',
        'productor': 'producer', 'especie': 'species', 'variedad': 'variety',
        'concepto fruta': 'fruit_type', 'embalaje': 'packaging', 'tipo': 'kind',
        'cant cajas': 'boxes', 'kg embalado': 'kilos', 'kg de exportacion': 'export_kilos',
        'calibre': 'caliber', 'referencia': 'reference',
    },
    _COMMERCIAL: {
        'tipo': 'kind', 'n op': 'folio', 'linea': 'line', 'productor': 'producer',
        'especie': 'species', 'variedad': 'variety', 'n bandejas': 'boxes', 'kg neto': 'kilos',
    },
    _YIELD: {'descripcion': 'concept', 'kilos': 'kilos'},
}


def process_rows(file, filename):
    workbook = open_excel(file, filename)
    grouped = defaultdict(lambda: defaultdict(list))
    overweight = {}
    try:
        sheet = workbook.worksheets[0]
        if sheet.max_row and sheet.max_row > 10050:
            raise UserError(_('Importe hasta 10.000 filas de procesos por archivo.'))
        section = None
        columns = {}
        for number, cells in enumerate(sheet.iter_rows(max_row=min(sheet.max_row or 10050, 10050),
                                                       max_col=40, values_only=True), 1):
            heading = header_key(cells[0])
            if heading.startswith('fruta iqf'):
                heading = _COMMERCIAL
            if any(normalized(cell).startswith('>>> total') for cell in cells):
                section = None
                continue
            if heading in _SECTIONS or (section != _YIELD and any(header_key(cell) == _YIELD for cell in cells)):
                section, columns = heading if heading in _SECTIONS else _YIELD, {}
            if not section or not any(cells):
                continue
            if not columns:
                headers = [header_key(value) for value in cells]
                expected = _SECTIONS[section]
                if all(headers.count(key) == 1 for key in expected):
                    columns = {target: headers.index(key) for key, target in expected.items()}
                continue
            row = {key: cells[index] for key, index in columns.items()}
            if section == _YIELD:
                concept = header_key(row['concept'])
                if concept == 'sobrepeso':
                    concept = 'sobre peso'
                if concept in _OVERWEIGHT:
                    try:
                        if concept in overweight:
                            raise ValueError
                        overweight[concept] = excel_number(row['kilos'])
                    except (TypeError, ValueError) as error:
                        raise UserError(_('Fila %s. Revise el valor o la repetición del concepto de sobrepeso.', number)) from error
                continue
            required = set(columns) - {'reference'}
            if any(not reference(row[key]) for key in required):
                raise UserError(_('Fila %s. Complete los datos de la tarja o pallet.', number))
            if section == _COMMERCIAL and reference(row['kind']) != '5':
                raise UserError(_('Fila %s. El tipo de fruta IQF debe ser 5 para importarlo como comercial.', number))
            for key in ('folio', 'line', 'tag'):
                if key in row:
                    row[key] = reference(row[key])
            try:
                boxes, kilos = excel_number(row['boxes']), excel_number(row['kilos'])
                if not boxes.is_integer() or boxes <= 0 or kilos <= 0:
                    raise ValueError
                if section == 'fruta embalada':
                    if isinstance(row['date'], datetime):
                        row['date'] = row['date'].date()
                    elif not isinstance(row['date'], date):
                        row['date'] = fields.Date.to_date(row['date'])
                    row['export_kilos'] = excel_number(row['export_kilos'])
                    if row['export_kilos'] <= 0 or header_key(row['kind']) != 'pallet':
                        raise ValueError
            except (TypeError, ValueError) as error:
                raise UserError(_('Fila %s. Revise la fecha, el tipo, las cajas o bandejas y los kilos.', number)) from error
            row.update(number=number, boxes=int(boxes), kilos=kilos)
            grouped[row['folio'], row['line']][section].append(row)
    finally:
        workbook.close()
    if not grouped or any(not (group.get('fruta procesada') and group.get('fruta embalada'))
                          for group in grouped.values()):
        raise UserError(_('Cada operación y línea debe contener fruta procesada y fruta embalada.'))
    if len(grouped) != 1 and any(overweight.values()):
        raise UserError(_('El sobrepeso de Rendimiento corresponde a todo el archivo. Separe el Excel por OP y línea.'))
    return grouped, sum(overweight.values())


class ExternalPackingProduction(models.Model):
    _inherit = 'step.packing.production'

    step_external_process_folio = fields.Char(string='OP externa', readonly=True, copy=False, index=True)
    step_external_process_line = fields.Char(string='Línea externa', readonly=True, copy=False)
    _sql_constraints = [
        ('external_process_unique', 'unique(company_id, packing_partner_id, date, step_external_process_folio, step_external_process_line)',
         'Esta operación externa y línea ya se importaron para esa fecha y packing.'),
    ]


class ExternalPackingOutput(models.Model):
    _inherit = 'stock.quant.package'

    step_external_pallet_reference = fields.Char(string='Referencia del pallet en el Excel', readonly=True, copy=False)
    step_external_pallet_export_kg = fields.Float(string='Kg de exportación informados',
        digits='Stock Weight', readonly=True, copy=False)


class ExternalPackingProcessImport(models.TransientModel):
    _name = 'step.external.packing.process.import'
    _description = 'Importar procesos de Packing por Excel'
    _check_company_auto = True

    company_id = fields.Many2one('res.company', readonly=True, default=lambda self: self.env.company, required=True)
    packing_id = fields.Many2one('res.partner', string='Planta', required=True, check_company=True,
        domain="[('step_export_packing', '=', True)]")
    template_id = fields.Many2one('step.external.fruit.reception.template', string='Plantilla',
        check_company=True, domain="[('company_id', '=', company_id)]")
    line_id = fields.Many2one('step.packing.line', string='Línea de proceso', required=True, check_company=True,
        domain="[('company_id', '=', company_id)]")
    process_type_id = fields.Many2one('step.packing.process.type', string='Tipo de proceso', required=True,
        domain="[('step_category', '=', 'packing')]")
    order_id = fields.Many2one('step.packing.order', string='OP de Odoo', check_company=True,
        domain="[('company_id', '=', company_id), ('state', '=', 'validated')]")
    file = fields.Binary(string='Archivo Excel', required=True, attachment=False)
    filename = fields.Char()
    commercial_product_id = fields.Many2one('product.product', string='Producto de fruta comercial',
        check_company=True,
        domain="[('is_storable', '=', True), ('tracking', '!=', 'serial'), ('uom_id.category_id', '=', weight_category_id)]")
    weight_category_id = fields.Many2one('uom.category', default=lambda self: self.env.ref('uom.product_uom_kgm').category_id)
    has_commercial = fields.Boolean(readonly=True)
    mapping_ids = fields.One2many('step.external.packing.process.mapping', 'wizard_id')
    reviewed = fields.Boolean(readonly=True)
    preview = fields.Char(readonly=True)

    @api.model
    def default_get(self, names):
        result = super().default_get(names)
        template = self.env['step.external.fruit.reception.template']._default_for_company()
        if template and 'template_id' in names and not result.get('template_id'):
            result['template_id'] = template.id
            if 'packing_id' in names and not result.get('packing_id'):
                result['packing_id'] = template.packing_id.id
        for field, model, domain in (
            ('line_id', 'step.packing.line', [('company_id', '=', self.env.company.id)]),
            ('process_type_id', 'step.packing.process.type', [('step_category', '=', 'packing')]),
        ):
            if field in names and not result.get(field):
                records = self.env[model].search(domain, limit=2)
                if len(records) == 1:
                    result[field] = records.id
        return result

    @api.onchange('template_id')
    def _onchange_template(self):
        if self.template_id:
            self.packing_id = self.template_id.packing_id
        self._clear_preview()

    @api.onchange('file')
    def _clear_preview(self):
        self.reviewed = False
        self.preview = False
        self.has_commercial = False
        self.mapping_ids = [Command.clear()]

    def _read_process(self):
        groups, overweight = process_rows(self.file, self.filename)
        if len({line for _, line in groups}) != 1:
            raise UserError(_('Separe el archivo por línea para seleccionar la línea de proceso de Odoo.'))
        return groups, overweight

    def action_review(self):
        self.ensure_one()
        groups, overweight = self._read_process()
        outputs = [row for group in groups.values() for row in group['fruta embalada']]
        commercial = sum(bool(group.get(_COMMERCIAL)) for group in groups.values())
        existing = {(row.kind, normalized(row.source)): row for row in self.mapping_ids}
        saved = {(row.kind, row.source_key): row for row in self.template_id.alias_ids}
        commands = [Command.clear()]
        masters = self.env['step.external.fruit.reception.import']
        for kind, model, field in (
                ('packaging', 'product.packaging', 'packaging_id'),
                ('caliber', 'step.management.fruit.caliber', 'caliber_id')):
            candidates = masters._masters(model)
            for source in sorted({reference(row[kind]) for row in outputs}):
                key = normalized(source)
                previous = existing.get((kind, key)) or saved.get(('process_' + kind, key))
                match = candidates.filtered(lambda item: normalized(item.name) == normalized(source))
                if kind == 'packaging' and not match:
                    match = candidates.filtered(lambda item: key in
                        {normalized(item.product_id.name), normalized(item.product_id.default_code)})
                elif kind == 'caliber' and not match:
                    match = candidates.filtered(lambda item: normalized(item.code) == key)
                chosen = previous[field] if previous and previous[field] in candidates else match
                commands.append(Command.create({'kind': kind, 'source': source,
                                                field: chosen.id if len(chosen) == 1 else False}))
        self.write({'reviewed': True, 'has_commercial': bool(commercial), 'mapping_ids': commands, 'preview':
            _('%(orders)s OT, %(inputs)s tarjas de entrada, %(outputs)s pallets y %(commercial)s tarjas comerciales. '
              'Sobrepeso total: %(overweight).2f kg.',
              orders=len(groups), inputs=sum(len(g['fruta procesada']) for g in groups.values()),
              outputs=len(outputs), commercial=commercial, overweight=overweight)})
        action = self.env.ref('step_packing_ticket_revision.action_external_packing_process_import').read()[0]
        action.update(res_id=self.id, views=[(action['view_id'][0], 'form')])
        return action

    def _check_input(self, tag, row):
        receipt = tag.step_process_reception_id
        detail = tag.step_tag_line_ids
        quantities = tag.quant_ids.filtered(lambda quant: quant.quantity > 0)
        stock_matches = detail.product_id == quantities.product_id and all(
            not float_compare(
                sum(detail.filtered(lambda line: line.product_id == product).mapped('quantity')),
                sum(quantities.filtered(lambda quant: quant.product_id == product).mapped('quantity')),
                precision_rounding=product.uom_id.rounding,
            )
            for product in detail.product_id
        )
        if (not receipt or receipt.state != 'done' or receipt.fruit_guide_number != reference(row['guide'])
                or tag.step_tag_kind != 'C' or tag.step_tag_state != 'validated'
                or normalized(tag.especie_id.name) != normalized(row['species'])
                or normalized(tag.variedad_id.name) != normalized(row['variety'])
                or float_compare(tag.step_actual_kg, row['kilos'], precision_digits=2)
                or float_compare(sum(tag.step_tag_line_ids.mapped('boxes')), row['boxes'], precision_digits=2)
                or not quantities or not stock_matches
                or _SELECTIONS['fruit_type'].get(normalized(row['fruit_type'])) != tag.fruit_type
                or any(tag.quant_ids.mapped('reserved_quantity'))):
            raise UserError(_('Fila %(row)s. La tarja %(tag)s debe coincidir con la guía, variedad, cajas y kilos de una recepción validada, y tener stock sin reservas.',
                              row=row['number'], tag=row['tag']))

    def _create_process(self, folio, line, group, mappings, overweight):
        raw, outputs = group['fruta procesada'], group['fruta embalada']
        commercial = group.get(_COMMERCIAL, [])
        packages = self.env['stock.quant.package']
        company = self.env.company
        inputs = packages
        for row in raw:
            tag = packages.search([('name', '=', row['tag']), ('company_id', '=', company.id),
                                   ('is_fruit_tag', '=', True), ('step_tag_kind', '=', 'C')], limit=2)
            if len(tag) != 1:
                raise UserError(_('Tarja %s no encontrada en la empresa activa. Valide primero su recepción.', row['tag']))
            self._check_input(tag, row)
            inputs |= tag
        dates = {row['date'] for row in outputs}
        identities = {tuple(normalized(row[key]) for key in ('producer', 'species', 'variety', 'fruit_type'))
                      for row in raw + outputs}
        if len(dates) != 1 or len(identities) != 1 or len(inputs.fundo_id) != 1 or len(inputs.step_producer_id) != 1:
            raise UserError(_('La OP externa %s debe tener una fecha, un productor, un fundo y una variedad.', folio))
        identity = next(iter(identities))[:3]
        for row in commercial:
            if tuple(normalized(row[key]) for key in ('producer', 'species', 'variety')) != identity:
                raise UserError(_('Fila %s. La fruta comercial debe coincidir con el productor, especie y variedad de la OP.', row['number']))
        if sum(row['kilos'] for row in outputs + commercial) > sum(row['kilos'] for row in raw) + 0.005:
            raise UserError(_('Los kilos de salida superan los kilos a proceso en la OP %s.', folio))
        if self.env['step.packing.production'].sudo().search_count([('company_id', '=', company.id),
                ('step_packing_input_tag_ids', 'in', inputs.ids)], limit=1):
            raise UserError(_('Alguna tarja de la OP %s ya está asignada a otra OT.', folio))

        first = inputs[0]
        products = inputs.step_tag_line_ids.product_id
        if len(products) != 1:
            raise UserError(_('La OP %s debe tener un solo producto de materia prima.', folio))
        ot = self.env['step.packing.production'].create({
            'company_id': company.id, 'packing_partner_id': self.packing_id.id, 'date': next(iter(dates)),
            'process_type_id': self.process_type_id.id, 'step_packing_line_id': self.line_id.id,
            'step_packing_order_id': self.order_id.id, 'raw_product_id': products.id,
            'fruit_fundo_id': first.fundo_id.id, 'fruit_grower_id': first.step_producer_id.id,
            'fruit_species_id': first.especie_id.id, 'fruit_variety_id': first.variedad_id.id,
            'step_external_process_folio': folio, 'step_external_process_line': line,
            'step_packing_input_tag_ids': [Command.set(inputs.ids)],
            'step_packing_overweight_kg': overweight,
        })
        kg = self.env.ref('uom.product_uom_kgm')
        tag_values = {
            'is_fruit_tag': True, 'step_packing_production_id': ot.id, 'step_packing_line_id': self.line_id.id,
            'step_producer_id': first.step_producer_id.id, 'fundo_id': first.fundo_id.id,
            'especie_id': first.especie_id.id, 'variedad_id': first.variedad_id.id, 'fruit_type': first.fruit_type,
        }
        for row in outputs:
            packaging = mappings['packaging', normalized(row['packaging'])].packaging_id
            caliber = mappings['caliber', normalized(row['caliber'])].caliber_id
            product = packaging.product_id
            if not product.is_storable or product.tracking == 'serial':
                raise UserError(_('Seleccione un embalaje con producto almacenable y sin seguimiento por serie.'))
            quantity = (kg._compute_quantity(row['kilos'], product.uom_id, round=False)
                        if product.uom_id.category_id == kg.category_id else row['boxes'])
            packages.create({
                **tag_values, 'name': row['tag'], 'step_tag_kind': 'E', 'step_packing_result': 'export',
                'step_packaging_id': packaging.id, 'fruit_caliber_id': caliber.id, 'box_count': row['boxes'],
                'step_external_pallet_reference': reference(row['reference']),
                'step_external_pallet_export_kg': row['export_kilos'],
                'step_tag_line_ids': [Command.create({'producer_id': first.step_producer_id.id,
                    'product_id': product.id, 'quantity': quantity, 'boxes': row['boxes'], 'kilos': row['kilos']})],
            })
        if commercial:
            product = self.commercial_product_id
            boxes = sum(row['boxes'] for row in commercial)
            kilos = sum(row['kilos'] for row in commercial)
            packages.create({
                **tag_values, 'name': folio, 'step_tag_kind': 'N', 'step_packing_result': 'commercial',
                'box_count': boxes,
                'step_tag_line_ids': [Command.create({'producer_id': first.step_producer_id.id,
                    'product_id': product.id, 'quantity': kg._compute_quantity(kilos, product.uom_id, round=False),
                    'boxes': boxes, 'kilos': kilos})],
            })
        ot._packing_stock_location(inputs)
        ot._check_packing_tags()
        return ot

    def action_import(self):
        self.ensure_one()
        company = self.env.company
        if (company != self.company_id or self.line_id.company_id != company
                or not self.packing_id.step_export_packing or self.process_type_id.step_category != 'packing'
                or self.order_id and (self.order_id.company_id != company or self.order_id.state != 'validated')):
            raise UserError(_('Seleccione una planta y una línea de la empresa activa y un tipo de proceso de embalaje.'))
        groups, overweight = self._read_process()
        if self.order_id and len({folio for folio, _ in groups}) != 1:
            raise UserError(_('Seleccione una OP de Odoo solo al importar una única OP externa.'))
        mappings = {(line.kind, normalized(line.source)): line for line in self.mapping_ids}
        seen = set()
        out_names = set()
        commercial_names = {folio for (folio, _line), group in groups.items() if group.get(_COMMERCIAL)}
        if commercial_names:
            product = self.commercial_product_id
            if (not product.active or not product.is_storable or product.tracking == 'serial'
                    or product.uom_id.category_id != self.env.ref('uom.product_uom_kgm').category_id):
                raise UserError(_('Seleccione un producto almacenable por peso y sin seguimiento por serie para la fruta comercial.'))
        masters = self.env['step.external.fruit.reception.import']
        packaging = masters._masters('product.packaging')
        calibers = masters._masters('step.management.fruit.caliber')
        for group in groups.values():
            for row in group['fruta procesada'] + group['fruta embalada']:
                if row['tag'] in seen:
                    raise UserError(_('La tarja %s se repite en el Excel. Revise los folios antes de importar.', row['tag']))
                seen.add(row['tag'])
            for row in group['fruta embalada']:
                out_names.add(row['tag'])
                selected_packaging = mappings.get(('packaging', normalized(row['packaging'])))
                selected_caliber = mappings.get(('caliber', normalized(row['caliber'])))
                if (not selected_packaging or not selected_packaging.packaging_id
                        or selected_packaging.packaging_id not in packaging
                        or not selected_caliber or not selected_caliber.caliber_id
                        or selected_caliber.caliber_id not in calibers):
                    raise UserError(_('Fila %s. Revise las equivalencias de embalaje y calibre.', row['number']))
        if out_names & commercial_names:
            raise UserError(_('Un folio de pallet coincide con el número de una tarja comercial en el Excel.'))
        for name in sorted(seen | commercial_names):
            self.env.cr.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))', ['steps-process-tag:' + name])
        if self.env['stock.quant.package'].sudo().search_count([
                ('step_tag_state', '!=', 'void'),
                '|', ('company_id', '=', company.id), ('step_packing_production_id.company_id', '=', company.id),
                '|', ('name', 'in', list(out_names)),
                '&', ('name', 'in', list(commercial_names)), ('step_tag_kind', 'in', ('E', 'N')),
        ], limit=1):
            raise UserError(_('Un folio de salida ya existe. Revise el Excel para evitar duplicados.'))
        with self.env.cr.savepoint():
            orders = self.env['step.packing.production']
            for (folio, line), group in groups.items():
                orders |= self._create_process(folio, line, group, mappings, overweight)
            if self.template_id:
                self.template_id._remember_aliases([
                    {'source': row.source, 'source_key': normalized(row.source), 'kind': 'process_' + row.kind,
                     'packaging_id': row.packaging_id.id, 'caliber_id': row.caliber_id.id}
                    for row in mappings.values() if row.packaging_id or row.caliber_id
                ])
        return {'type': 'ir.actions.act_window', 'name': _('Órdenes de trabajo importadas'),
                'res_model': orders._name, 'views': [(False, 'list'), (False, 'form')],
                'domain': [('id', 'in', orders.ids)]}


class ExternalPackingProcessMapping(models.TransientModel):
    _name = 'step.external.packing.process.mapping'
    _description = 'Equivalencia del Excel de Packing'
    _order = 'kind, source'

    wizard_id = fields.Many2one('step.external.packing.process.import', required=True, ondelete='cascade')
    kind = fields.Selection([('packaging', 'Embalaje'), ('caliber', 'Calibre')], required=True)
    source = fields.Char(required=True)
    packaging_id = fields.Many2one('product.packaging', string='Embalaje')
    caliber_id = fields.Many2one('step.management.fruit.caliber', string='Calibre')
