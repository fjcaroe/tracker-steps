"""Receipt cohorts, native closed OT yields and duplicate-safe advance creation."""
from collections import defaultdict
from datetime import datetime, time, timedelta

import pytz

from odoo import api, Command, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.osv import expression
from odoo.tools import float_compare
from odoo.addons.step_packing_fruit_proforma.purchase import _controlled
from odoo.addons.step_packing_fruit_proforma.species import purchase_taxes
from .claims import BASIS, lock_companies, source_key


class PrepareAdvance(models.TransientModel):
    _name = 'step.producer.advance.prepare'
    _description = 'Preparar proformas de anticipo productor'

    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    producer_ids = fields.Many2many('res.partner', string='Productores', domain=[('is_productor', '=', True)])
    species_ids = fields.Many2many('step.especie', string='Especies')
    date_from = fields.Date('Desde recepción', required=True,
        default=lambda self: fields.Date.context_today(self) - timedelta(days=6),
        help='Para cada recepción se considera la fecha más antigua entre la prevista y la efectiva.')
    date_to = fields.Date('Hasta recepción', required=True, default=fields.Date.context_today)
    basis = fields.Selection(BASIS, string='Calcular por', default='processed', required=True)
    process_cutoff = fields.Date('Fecha corte proceso', default=fields.Date.context_today,
        help='Incluye la exportación de OT cerradas según su Fecha de proceso (Date Packing), hasta este corte. En una OT mixta, los kilos exportados se distribuyen según los kilos de entrada de cada recepción.')
    proforma_date = fields.Date('Fecha proforma', required=True, default=fields.Date.context_today)
    net_due = fields.Date('Fecha de pago Neto', required=True)
    vat_due = fields.Date('Fecha de pago IVA', required=True)
    pricelist_id = fields.Many2one('product.pricelist', string='Lista de precios', required=True,
        domain="[('step_advance_price','=',True),('step_advance_company_ids','in',company_id)]")
    excluded_product_ids = fields.Many2many(
        'product.product', 'step_adv_prepare_excluded_product_rel', string='Productos excluidos',
        domain="['|', ('company_id', '=', False), ('company_id', 'parent_of', company_id)]",
        help='Se omiten los productos valorizados seleccionados al preparar este anticipo.')

    def _validate_selection(self):
        self.ensure_one()
        self.check_access('write')
        if not self.env.user.has_group('account.group_account_user'):
            raise UserError(_('La preparación de anticipos requiere permisos de Contabilidad.'))
        if (self.company_id not in self.env.companies or self.date_to < self.date_from
                or not self.net_due or not self.vat_due):
            raise ValidationError(_('Seleccione una compañía activa, un período válido y ambas fechas de pago.'))
        if self.basis == 'processed' and (not self.process_cutoff or self.process_cutoff < self.date_to):
            raise ValidationError(_('El corte de proceso debe ser igual o posterior al Hasta de recepción.'))
        self.pricelist_id.check_access('read')
        if not self.pricelist_id.step_advance_price or self.company_id not in self.pricelist_id.step_advance_company_ids:
            raise ValidationError(_('La lista debe corresponder a anticipos y estar disponible para la compañía.'))
        self.excluded_product_ids.check_access('read')
        if any(product.company_id and not self.company_id.parent_path.startswith(product.company_id.parent_path)
               for product in self.excluded_product_ids):
            raise ValidationError(_('Seleccione productos disponibles para la compañía del anticipo.'))

    def _bounds(self):
        zone = pytz.timezone(self.env.context.get('tz') or self.env.user.tz or 'UTC')
        return tuple(zone.localize(datetime.combine(day, time.min)).astimezone(pytz.UTC).replace(tzinfo=None)
                     for day in (self.date_from, self.date_to + timedelta(days=1)))

    def _receipt_day(self, receipt):
        dates = [value for value in (receipt.scheduled_date, receipt.date_done) if value]
        if not dates:
            raise ValidationError(_('La recepción no tiene fecha prevista ni efectiva.'))
        return fields.Datetime.context_timestamp(self, min(dates)).date()

    def _receipt_sources(self):
        """Select the first available receipt date in the user's local period."""
        start, end = self._bounds()
        domain = [('company_id', '=', self.company_id.id), ('state', '=', 'done'),
                  ('picking_type_code', '=', 'incoming'), ('step_fruit_reception_kind', 'in', ['process', 'packed'])]
        names = ('scheduled_date', 'date_done')
        # At least one known date must be in the period, and neither may
        # precede its start. Keep the filtering in the native picking query.
        domain = expression.AND([domain,
            expression.OR([[(name, '>=', start), (name, '<', end)] for name in names]),
            *[expression.OR([[(name, '=', False)], [(name, '>=', start)]]) for name in names],
        ])
        if self.producer_ids:
            domain = expression.AND([domain, expression.OR([
                [('fruit_fundo_id.partner_id', 'in', self.producer_ids.ids)],
                [('fruit_fundo_id', '=', False), ('partner_id', 'in', self.producer_ids.ids)],
            ])])
        if self.species_ids:
            domain.append(('fruit_species_id', 'in', self.species_ids.ids))
        return self.env['stock.picking'].search(domain, order='scheduled_date,id')

    def _origin_receipts(self, tag, memo, visiting=None):
        if tag.id in memo:
            return memo[tag.id]
        visiting = set(visiting or ())
        if tag.id in visiting:
            raise ValidationError(_('La trazabilidad de la tarja contiene un ciclo.'))
        visiting.add(tag.id)
        receipts = tag.step_reception_tag_line_ids.picking_id.filtered(
            lambda row: row.company_id == self.company_id and row.state == 'done'
            and row.picking_type_code == 'incoming' and row.step_fruit_reception_kind == 'process')
        if not receipts:
            for parent in tag.step_tag_line_ids.source_package_id:
                receipts |= self._origin_receipts(parent, memo, visiting)
        memo[tag.id] = receipts
        return receipts

    def _source_rows(self):
        receipts = self._receipt_sources()
        if self.basis == 'received':
            return self._received_rows(receipts)
        raw = receipts.filtered(lambda row: row.step_fruit_reception_kind == 'process').fruit_tag_line_ids.package_id
        # This native process date is also displayed on output tags as Date
        # Packing. Registration timestamps and the tag's generic pack date do
        # not determine the cutoff for the closed production order.
        orders = self.env['step.packing.production'].search([
            ('company_id', '=', self.company_id.id), ('state', 'in', ['closed', 'costed', 'accounted']),
            ('date', '<=', self.process_cutoff),
            ('step_packing_input_tag_ids', 'in', raw._advance_raw_descendants(self.company_id).ids)], order='id')
        orders._lock_process()
        packed = receipts.filtered(lambda row: row.step_fruit_reception_kind == 'packed').fruit_tag_line_ids.package_id
        tags = orders.step_packing_output_tag_ids.filtered(lambda tag: tag.step_tag_kind == 'E') | packed.filtered(
            lambda tag: tag.step_tag_kind == 'E' and not tag.step_packing_production_id)
        if tags:
            tags.flush_recordset()
            self.env.cr.execute('SELECT id FROM stock_quant_package WHERE id=ANY(%s) ORDER BY id FOR UPDATE', [tags.ids])
            tags.invalidate_recordset()
        rows, memo = [], {}
        for order in orders:
            if order.purchase_bill_id and order.purchase_bill_id.state != 'cancel':
                continue
            inputs = order.step_packing_input_tag_ids
            input_kg = sum(inputs.mapped('step_actual_kg'))
            if input_kg <= 0:
                raise ValidationError(_('La OT %s no tiene kilos de entrada positivos.') % order.name)
            for source in inputs:
                origins = self._origin_receipts(source, memo)
                if len(origins) != 1:
                    raise UserError(_('La tarja de entrada %s debe identificar una única recepción de origen para distribuir los kilos de exportación.') % source.display_name)
                receipt = origins
                if receipt not in receipts:
                    continue
                for tag in order.step_packing_output_tag_ids.filtered(lambda item: item in tags):
                    for detail in tag.step_tag_line_ids:
                        row = self._row(tag, detail, receipt, order, source)
                        row.update(quantity=detail.kilos * source.step_actual_kg / input_kg,
                                   received_kg=source.step_actual_kg * detail.kilos / max(order.step_packing_export_kg, 0.000001),
                                   export_ratio=order.step_packing_export_kg / input_kg)
                        rows.append(row)
        for receipt in receipts.filtered(lambda item: item.step_fruit_reception_kind == 'packed'):
            for tag in receipt.fruit_tag_line_ids.package_id.filtered(lambda item: item in packed and not item.step_packing_production_id):
                if tag.step_tag_kind != 'E':
                    continue
                for detail in tag.step_tag_line_ids:
                    row = self._row(tag, detail, receipt)
                    row.update(quantity=detail.kilos, received_kg=detail.kilos, export_ratio=1.0)
                    rows.append(row)
        unique = {}
        for row in rows:
            key = source_key(row)
            if key in unique:
                raise UserError(_('La fuente de una tarja aparece en más de una recepción u OT. Revise su trazabilidad.'))
            unique[key] = row
        return list(unique.values())

    def _received_rows(self, receipts):
        rows = []
        for receipt in receipts:
            kind = 'C' if receipt.step_fruit_reception_kind == 'process' else 'E'
            for tag, receipt_lines in receipt.fruit_tag_line_ids.grouped('package_id').items():
                if (not tag or tag.step_tag_kind != kind or tag.step_packing_production_id
                        or tag.step_tag_state in ('created', 'void', 'liquidated')):
                    continue
                origins = tag.step_reception_tag_line_ids.picking_id.filtered(lambda picking:
                    picking.state == 'done' and picking.company_id == self.company_id
                    and picking.picking_type_code == 'incoming' and picking.step_fruit_reception_kind)
                details = tag.step_tag_line_ids
                if (origins != receipt or not details
                        or float_compare(sum(details.mapped('kilos')), sum(receipt_lines.mapped('kilos')),
                                         precision_digits=2)):
                    raise UserError(_('La tarja %s debe identificar una única recepción validada y coincidir con sus kilos netos.') % tag.display_name)
                for detail in details:
                    row = self._row(tag, detail, receipt)
                    row.update(quantity=detail.kilos, received_kg=detail.kilos, export_ratio=0.0)
                    rows.append(row)
        return rows

    def _row(self, tag, detail, receipt, production=None, source=None):
        # Native packages can lose their quant-derived company after shipment.
        # The closed OT / completed incoming receipt remains authoritative.
        company = tag.company_id or (production.company_id if production else receipt.company_id)
        origin = source or tag
        fundo = receipt.fruit_fundo_id or origin.fundo_id
        producer = receipt.fruit_fundo_id.partner_id or receipt.partner_id
        if not receipt.fruit_fundo_id and (not producer.is_productor or origin.step_producer_id != producer
                or fundo and fundo.partner_id != producer):
            raise UserError(_('La recepción sin fundo debe identificar el mismo productor que su tarja de origen. Revise la recepción de %s.') % origin.display_name)
        if (company != self.company_id or receipt.company_id != self.company_id
                or detail.producer_id != producer
                or self.producer_ids and detail.producer_id not in self.producer_ids
                or self.species_ids and tag.especie_id not in self.species_ids
                or not tag.especie_id or detail.kilos <= 0
                or tag.step_tag_state in ('created', 'void', 'liquidated')):
            raise UserError(_('Revise productor, compañía, especie, estado y kilos de la tarja %s.') % tag.display_name)
        packaging = tag.step_packaging_id
        if not packaging:
            # Historical E tags can predate the packaging relation. Only an
            # unambiguous native packaging of this exact product can fill it.
            candidates = detail.product_id.packaging_ids.filtered(lambda item: not item.company_id
                or self.company_id.parent_path.startswith(item.company_id.parent_path))
            if len(candidates) == 1:
                packaging = candidates
        return {'tag_id': tag.id, 'tag_name': tag.name, 'tag_line_id': detail.id,
            'input_tag_id': source.id if source else 0,
            'receipt_id': receipt.id, 'receipt_ids': receipt.ids,
            'receipt_guides': [receipt.fruit_guide_number] if receipt.fruit_guide_number else [],
            'receipt_day': str(self._receipt_day(receipt)), 'fundo_id': fundo.id,
            'fundo_name': fundo.display_name or '',
            'production_id': production.id if production else 0, 'ot_name': production.name if production else '',
            'packing_day': fields.Date.to_string(production.date) if production else False,
            'producer_id': detail.producer_id.id, 'species_id': tag.especie_id.id,
            'variety_id': tag.variedad_id.id, 'variety_name': tag.variedad_id.display_name or '',
            'priced_product_id': detail.product_id.id, 'priced_product_name': detail.product_id.display_name,
            'market_id': tag.step_advance_market_id.id, 'market_name': tag.step_advance_market_id.display_name or '',
            'packaging_id': packaging.id, 'packaging_name': packaging.display_name or ''}

    def _price_rows(self, rows):
        kg = self.env.ref('uom.product_uom_kgm')
        currency = self.pricelist_id.currency_id
        if currency != self.company_id.currency_id:
            ancestors = self.company_id.sudo().search([('id', 'parent_of', self.company_id.id)])
            if not self.env['res.currency.rate'].search_count([
                    ('currency_id', '=', currency.id), ('name', '<=', self.proforma_date),
                    '|', ('company_id', '=', False), ('company_id', 'in', ancestors.ids)], limit=1):
                raise UserError(_('Configure el tipo de cambio de la moneda de la lista para la fecha de proforma.'))
        for row in rows:
            product = self.env['product.product'].browse(row['priced_product_id']).with_company(self.company_id)
            market = self.env['step.fruit.market'].browse(row['market_id'])
            packaging = self.env['product.packaging'].browse(row['packaging_id'])
            species = self.env['step.especie'].browse(row['species_id'])
            variety = self.env['step.variedad'].browse(row['variety_id'])
            price, rule = self.pricelist_id.with_context(
                advance_variety_group=variety.grupo_variedad_id.id, advance_basis=self.basis)._advance_price(
                product, market, packaging, row['quantity'], fields.Date.to_date(row['receipt_day']), species)
            base = product.product_tmpl_id.step_export_base_product_id
            if base and len(base.product_variant_ids) != 1:
                raise UserError(_('El producto base debe identificar una única variante para facturar por kg.'))
            billed = (base.product_variant_ids if base else product).with_company(self.company_id)
            if billed.uom_id.category_id != kg.category_id:
                raise UserError(_('Vincule %s con su producto base de compra en unidad de peso antes de facturar por kg.') % product.display_name)
            account = billed.property_account_expense_id or billed.categ_id.property_account_expense_categ_id
            if not account or account.deprecated:
                raise UserError(_('Configure la cuenta de compra del producto o su categoría: %s.') % billed.display_name)
            subject, retention = species._fruit_vat_policy_for(self.company_id, validate=True)
            taxes = purchase_taxes(billed, self.company_id, subject, retention)
            converted = self.pricelist_id.currency_id._convert(price, self.company_id.currency_id,
                self.company_id, self.proforma_date, round=False)
            row.update(product_id=billed.id, product_name=billed.display_name, uom_id=kg.id, uom_name=kg.display_name,
                price_unit=converted, amount=converted * row['quantity'], source_price=price,
                source_amount=price * row['quantity'], price_rule_id=rule.id,
                expense_id=account.id, tax_ids=taxes.ids, dte='46' if subject else '33', retention_id=retention.id)
        return rows

    def action_prepare(self):
        self._validate_selection()
        # Keep every date/currency/company lookup in the selected legal company.
        wizard = self.with_company(self.company_id)
        with self.env.cr.savepoint():
            lock_companies(wizard.company_id)
            wizard.pricelist_id.flush_recordset()
            wizard.env.cr.execute('SELECT id FROM product_pricelist WHERE id=%s FOR SHARE', [self.pricelist_id.id])
            if wizard.pricelist_id.item_ids:
                wizard.env.cr.execute('SELECT id FROM product_pricelist_item WHERE id=ANY(%s) ORDER BY id FOR SHARE',
                                      [wizard.pricelist_id.item_ids.ids])
            sources = wizard._source_rows()
            excluded = set(wizard.excluded_product_ids.ids)
            rows = [row for row in sources if row['priced_product_id'] not in excluded]
            if sources and not rows:
                raise UserError(_('No quedan kilos para preparar después de excluir los productos seleccionados.'))
            result = wizard.env['purchase.order']
            exact, blocked_tags, blocked_roots, origins = result._advance_reservations(
                wizard.company_id, wizard.basis, rows)
            fresh = []
            existing_with_exclusions = False
            for row in rows:
                existing = result.browse(exact.get(source_key(row)))
                if existing:
                    if existing.has_access('read') and (existing.step_advance_basis or 'processed') == wizard.basis:
                        if excluded.intersection(existing.order_line.step_advance_priced_product_id.ids):
                            existing_with_exclusions = True
                        else:
                            result |= existing
                elif (row['tag_id'] not in blocked_tags
                        and not blocked_roots.intersection(origins.get(row.get('input_tag_id') or row['tag_id'], ()))):
                    fresh.append(row)
            groups = defaultdict(list)
            for row in wizard._price_rows(fresh) if fresh else []:
                groups[(row['producer_id'], row['species_id'], row['dte'], row['retention_id'])].append(row)
            for key, incoming in groups.items():
                result |= wizard._prepare_group(key, incoming)
            if not result:
                if existing_with_exclusions:
                    raise UserError(_('Los kilos disponibles ya están en proformas que incluyen productos excluidos. Revise esas proformas antes de volver a preparar los kilos.'))
                raise UserError(_('No hay kilos disponibles para el cálculo seleccionado. Revise las recepciones, las proformas existentes y, si corresponde, el corte de proceso.'))
            result.filtered(lambda order: order.step_fruit_state == 'draft').action_fruit_refresh_taxes()
            return result._fruit_action()

    def _prepare_group(self, key, rows):
        producer, species, dte, retention = key
        company = self.company_id
        cutoff = self.process_cutoff if self.basis == 'processed' else False
        warehouse = self.env['stock.warehouse'].search([('company_id', '=', company.id)], limit=1)
        if not warehouse:
            raise UserError(_('La compañía requiere su bodega nativa para preparar la compra sin movimientos de stock.'))
        drafts = self.env['purchase.order'].search([
            ('step_advance_proforma', '=', True), ('company_id', '=', company.id),
            ('partner_id', '=', producer), ('step_fruit_species_id', '=', species),
            ('step_fruit_period_start', '=', self.date_from), ('step_fruit_period_end', '=', self.date_to),
            ('step_advance_pricelist_id', '=', self.pricelist_id.id), ('step_fruit_state', '=', 'draft'),
            ('step_advance_net_due', '=', self.net_due), ('step_advance_vat_due', '=', self.vat_due),
            ('step_advance_basis', '=', self.basis), ('step_advance_cutoff', '=', cutoff),
            ('date_order', '=', fields.Datetime.to_datetime(self.proforma_date)),
            ('step_fruit_dte_code', '=', dte), ('step_fruit_withholding_tax_id', '=', retention or False)])
        order = drafts.filtered(lambda draft: draft.step_advance_excluded_product_ids == self.excluded_product_ids)[:1]
        if not order:
            rate = self.pricelist_id.currency_id._convert(1, company.currency_id, company, self.proforma_date, round=False)
            order = _controlled(self.env['purchase.order']).create({
                'step_fruit_proforma': True, 'step_advance_proforma': True,
                'name': self.env['ir.sequence'].next_by_code('step.producer.advance.' + dte),
                'partner_id': producer, 'company_id': company.id, 'currency_id': company.currency_id.id,
                'picking_type_id': warehouse.in_type_id.id, 'date_order': fields.Datetime.to_datetime(self.proforma_date),
                'step_fruit_species_id': species, 'step_fruit_dte_code': dte,
                'step_fruit_period_start': self.date_from, 'step_fruit_period_end': self.date_to,
                'step_fruit_withholding_tax_id': retention or False,
                'step_advance_pricelist_id': self.pricelist_id.id, 'step_advance_basis': self.basis,
                'step_advance_excluded_product_ids': [Command.set(self.excluded_product_ids.ids)],
                'step_advance_cutoff': cutoff,
                'step_advance_net_due': self.net_due, 'step_advance_vat_due': self.vat_due,
                'step_advance_source_currency_id': self.pricelist_id.currency_id.id, 'step_advance_exchange_rate': rate})
        order._fruit_lock()
        all_rows = [row for line in order.order_line for row in line.step_fruit_source_rows or []] + rows
        lines = defaultdict(list)
        for row in all_rows:
            lines[(row['priced_product_id'], row['product_id'], row['market_id'], row['packaging_id'],
                   row['source_price'], row['price_unit'], row['expense_id'], tuple(row['tax_ids']))].append(row)
        commands = [Command.clear()]
        for (priced, billed, market, packaging, source_price, price, expense, taxes), sources in lines.items():
            mapped = self.env['account.tax'].browse(taxes)
            if order.fiscal_position_id:
                mapped = order.fiscal_position_id.map_tax(mapped)
            commands.append(Command.create({
                'product_id': billed, 'name': _('Anticipo kg - %s') % sources[0]['priced_product_name'],
                'product_qty': sum(row['quantity'] for row in sources), 'product_uom': self.env.ref('uom.product_uom_kgm').id,
                'price_unit': price, 'date_planned': order.date_order, 'taxes_id': [Command.set(mapped.ids)],
                'step_fruit_expense_account_id': expense, 'step_fruit_source_rows': sources,
                'step_fruit_tag_line_ids': [Command.set(sorted({row['tag_line_id'] for row in sources}))],
                'step_advance_priced_product_id': priced, 'step_advance_market_id': market or False,
                'step_advance_packaging_id': packaging or False}))
        # Rebuild only an unapproved draft; its immutable sources and prices are
        # retained while newly arrived receipts can join the same review batch.
        _controlled(order).write({
            'order_line': commands,
            'step_fruit_tag_ids': [Command.set(sorted({row['tag_id'] for row in all_rows}))],
            'step_fruit_production_ids': [Command.set(sorted({row['production_id'] for row in all_rows if row['production_id']}))],
            'step_fruit_receipt_ids': [Command.set(sorted({row['receipt_id'] for row in all_rows}))],
            'step_fruit_guide_refs': ', '.join(sorted({guide for row in all_rows for guide in row['receipt_guides']}))})
        order._fruit_check_sources()
        for line in order.order_line:
            if company.currency_id.compare_amounts(line.price_subtotal,
                    company.currency_id.round(line.product_qty * line.price_unit)):
                raise ValidationError(_('La lista expresa precios netos. Revise los impuestos incluidos en el precio y la posición fiscal; no se guardó una proforma con otro neto.'))
        return order
