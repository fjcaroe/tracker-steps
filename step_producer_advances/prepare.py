"""Receipt cohorts, native closed OT yields and duplicate-safe advance creation."""
from collections import defaultdict
from datetime import datetime, time, timedelta

import pytz

from odoo import api, Command, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.addons.step_packing_fruit_proforma.purchase import _controlled
from odoo.addons.step_packing_fruit_proforma.species import purchase_taxes
from .purchase import source_key


class PrepareAdvance(models.TransientModel):
    _name = 'step.producer.advance.prepare'
    _description = 'Preparar proformas de anticipo productor'

    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    producer_ids = fields.Many2many('res.partner', string='Productores', domain=[('is_productor', '=', True)])
    species_ids = fields.Many2many('step.especie', string='Especies')
    date_from = fields.Date('Desde recepción', required=True,
        default=lambda self: fields.Date.context_today(self) - timedelta(days=6))
    date_to = fields.Date('Hasta recepción', required=True, default=fields.Date.context_today)
    process_cutoff = fields.Date('Fecha corte proceso', required=True, default=fields.Date.context_today,
        help='Incluye exportación de procesos cerrados hasta esta fecha, solo de las recepciones seleccionadas. En una OT mixta, los kilos exportados se distribuyen según los kilos de entrada de cada recepción.')
    proforma_date = fields.Date('Fecha proforma', required=True, default=fields.Date.context_today)
    net_due = fields.Date('Fecha de pago Neto', required=True)
    vat_due = fields.Date('Fecha de pago IVA', required=True)
    pricelist_id = fields.Many2one('product.pricelist', string='Lista de precios', required=True,
        domain="[('step_advance_price','=',True),('step_advance_company_ids','in',company_id)]")

    def _validate_selection(self):
        self.ensure_one()
        self.check_access('write')
        if not self.env.user.has_group('account.group_account_user'):
            raise UserError(_('La preparación de anticipos requiere permisos de Contabilidad.'))
        if (self.company_id not in self.env.companies or self.date_to < self.date_from
                or self.process_cutoff < self.date_to or not self.net_due or not self.vat_due):
            raise ValidationError(_('Seleccione una compañía activa, un período válido, corte igual o posterior al Hasta y ambas fechas de pago.'))
        self.pricelist_id.check_access('read')
        if not self.pricelist_id.step_advance_price or self.company_id not in self.pricelist_id.step_advance_company_ids:
            raise ValidationError(_('La lista debe corresponder a anticipos y estar disponible para la compañía.'))

    def _bounds(self):
        zone = pytz.timezone(self.env.context.get('tz') or self.env.user.tz or 'UTC')
        return tuple(zone.localize(datetime.combine(day, time.min)).astimezone(pytz.UTC).replace(tzinfo=None)
                     for day in (self.date_from, self.date_to + timedelta(days=1)))

    def _receipt_day(self, receipt):
        return fields.Datetime.context_timestamp(self, receipt.scheduled_date).date()

    def _receipt_sources(self):
        """Read the same local scheduled reception date as the producer report."""
        start, end = self._bounds()
        domain = [('company_id', '=', self.company_id.id), ('state', '=', 'done'),
                  ('picking_type_code', '=', 'incoming'), ('step_fruit_reception_kind', 'in', ['process', 'packed']),
                  ('scheduled_date', '>=', start), ('scheduled_date', '<', end)]
        if self.producer_ids:
            domain.append(('fruit_fundo_id.partner_id', 'in', self.producer_ids.ids))
        if self.species_ids:
            domain.append(('fruit_species_id', 'in', self.species_ids.ids))
        return self.env['stock.picking'].search(domain, order='scheduled_date,id')

    def _raw_descendants(self, original):
        seen, frontier = original, original
        while frontier:
            children = self.env['step.fruit.package.line'].search([
                ('source_package_id', 'in', frontier.ids), ('package_id.company_id', '=', self.company_id.id),
                ('package_id.step_tag_kind', '=', 'C')]).package_id
            frontier = children - seen
            seen |= frontier
        return seen

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
        raw = receipts.filtered(lambda row: row.step_fruit_reception_kind == 'process').fruit_tag_line_ids.package_id
        orders = self.env['step.packing.production'].search([
            ('company_id', '=', self.company_id.id), ('state', 'in', ['closed', 'costed', 'accounted']),
            ('date', '<=', self.process_cutoff), ('step_packing_input_tag_ids', 'in', self._raw_descendants(raw).ids)], order='id')
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

    def _row(self, tag, detail, receipt, production=None, source=None):
        # Native packages can lose their quant-derived company after shipment.
        # The closed OT / completed incoming receipt remains authoritative.
        company = tag.company_id or (production.company_id if production else receipt.company_id)
        if (company != self.company_id or receipt.company_id != self.company_id
                or detail.producer_id != receipt.fruit_fundo_id.partner_id
                or self.producer_ids and detail.producer_id not in self.producer_ids
                or self.species_ids and tag.especie_id not in self.species_ids
                or not tag.especie_id or detail.kilos <= 0
                or tag.step_tag_state in ('created', 'void', 'liquidated')):
            raise UserError(_('Revise productor, compañía, especie, estado y kilos de la tarja %s.') % tag.display_name)
        return {'tag_id': tag.id, 'tag_name': tag.name, 'tag_line_id': detail.id,
            'input_tag_id': source.id if source else 0,
            'receipt_id': receipt.id, 'receipt_ids': receipt.ids,
            'receipt_guides': [receipt.fruit_guide_number] if receipt.fruit_guide_number else [],
            'receipt_day': str(self._receipt_day(receipt)), 'fundo_id': receipt.fruit_fundo_id.id,
            'fundo_name': receipt.fruit_fundo_id.display_name,
            'production_id': production.id if production else 0, 'ot_name': production.name if production else '',
            'producer_id': detail.producer_id.id, 'species_id': tag.especie_id.id,
            'variety_id': tag.variedad_id.id, 'variety_name': tag.variedad_id.display_name or '',
            'priced_product_id': detail.product_id.id, 'priced_product_name': detail.product_id.display_name,
            'market_id': tag.step_advance_market_id.id, 'market_name': tag.step_advance_market_id.display_name or '',
            'packaging_id': tag.step_packaging_id.id, 'packaging_name': tag.step_packaging_id.display_name or ''}

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
            price, rule = self.pricelist_id.with_context(advance_variety_group=variety.grupo_variedad_id.id)._advance_price(
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
            wizard.env.cr.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',
                                  ['step-producer-advance:%s' % self.company_id.id])
            wizard.pricelist_id.flush_recordset()
            wizard.env.cr.execute('SELECT id FROM product_pricelist WHERE id=%s FOR SHARE', [self.pricelist_id.id])
            if wizard.pricelist_id.item_ids:
                wizard.env.cr.execute('SELECT id FROM product_pricelist_item WHERE id=ANY(%s) ORDER BY id FOR SHARE',
                                      [wizard.pricelist_id.item_ids.ids])
            rows = wizard._source_rows()
            tags = wizard.env['stock.quant.package'].browse(sorted({row['tag_id'] for row in rows}))
            existing = wizard.env['purchase.order'].search([
                ('company_id', '=', self.company_id.id), ('step_advance_proforma', '=', True),
                ('step_fruit_state', '!=', 'cancel'), ('step_fruit_tag_ids', 'in', tags.ids)])
            reserved = {source_key(row): order for order in existing for line in order.order_line
                        for row in line.step_fruit_source_rows or []}
            result = wizard.env['purchase.order']
            fresh = []
            for row in rows:
                tag = wizard.env['stock.quant.package'].browse(row['tag_id'])
                if tag.step_fruit_proforma_id and tag.step_fruit_proforma_id.step_fruit_state != 'cancel':
                    continue
                if source_key(row) in reserved:
                    result |= reserved[source_key(row)]
                else:
                    fresh.append(row)
            groups = defaultdict(list)
            for row in wizard._price_rows(fresh):
                groups[(row['producer_id'], row['species_id'], row['dte'], row['retention_id'])].append(row)
            for key, incoming in groups.items():
                result |= wizard._prepare_group(key, incoming)
            if not result:
                raise UserError(_('No hay kilos de exportación disponibles en las recepciones y corte seleccionados. Revise procesos pendientes, documentos mensuales y anticipos existentes.'))
            result.filtered(lambda order: order.step_fruit_state == 'draft').action_fruit_refresh_taxes()
            return result._fruit_action()

    def _prepare_group(self, key, rows):
        producer, species, dte, retention = key
        company = self.company_id
        warehouse = self.env['stock.warehouse'].search([('company_id', '=', company.id)], limit=1)
        if not warehouse:
            raise UserError(_('La compañía requiere su bodega nativa para preparar la compra sin movimientos de stock.'))
        order = self.env['purchase.order'].search([
            ('step_advance_proforma', '=', True), ('company_id', '=', company.id),
            ('partner_id', '=', producer), ('step_fruit_species_id', '=', species),
            ('step_fruit_period_start', '=', self.date_from), ('step_fruit_period_end', '=', self.date_to),
            ('step_advance_pricelist_id', '=', self.pricelist_id.id), ('step_fruit_state', '=', 'draft'),
            ('step_advance_net_due', '=', self.net_due), ('step_advance_vat_due', '=', self.vat_due),
            ('step_advance_cutoff', '=', self.process_cutoff), ('date_order', '=', fields.Datetime.to_datetime(self.proforma_date)),
            ('step_fruit_dte_code', '=', dte), ('step_fruit_withholding_tax_id', '=', retention or False)], limit=1)
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
                'step_advance_pricelist_id': self.pricelist_id.id, 'step_advance_cutoff': self.process_cutoff,
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
