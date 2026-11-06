"""Prepare native purchase proformas from closed fruit operations."""
from collections import defaultdict

from odoo import Command, fields, models, _
from odoo.exceptions import UserError, ValidationError

from .guards import _FRUIT
from .purchase import PurchaseOrder


class Production(models.Model):
    _inherit = 'step.packing.production'

    step_fruit_proforma_ids = fields.Many2many(
        'purchase.order', 'step_fruit_proforma_production_rel', 'production_id', 'order_id',
        string='Proformas productor', readonly=True, copy=False)


class ProformaReceipts(models.Model):
    _inherit = 'purchase.order'
    _FRUIT_SOURCE_FIELDS = PurchaseOrder._FRUIT_SOURCE_FIELDS | {'step_fruit_receipt_ids'}

    step_fruit_receipt_ids = fields.Many2many(
        'stock.picking', string='Recepciones de origen', readonly=True, copy=False)


class MonthlyFruitProforma(models.TransientModel):
    _inherit = 'step.packing.monthly.fruit.bill'

    def _fruit_orders(self):
        self.ensure_one()
        if not self.env.user.has_group('account.group_account_user'):
            raise UserError(_('La preparación de proformas requiere permisos de Contabilidad.'))
        if (self.company_id not in self.env.companies or self.date_end < self.date_start
                or self.date_start.strftime('%Y-%m') != self.date_end.strftime('%Y-%m')):
            raise ValidationError(_('Seleccione una empresa habilitada y un período dentro del mismo mes.'))
        domain = [('company_id', '=', self.company_id.id),
                  ('state', 'in', ['closed', 'costed', 'accounted']),
                  ('date', '>=', self.date_start), ('date', '<=', self.date_end)]
        if self.producer_ids:
            domain.append(('fruit_grower_id', 'in', self.producer_ids.ids))
        if self.contract_id:
            self.contract_id.check_access('read')
            if self.producer_ids and self.producer_ids != self.contract_id.partner_id:
                raise ValidationError(_('Seleccione solo el productor del contrato indicado.'))
            domain.append(('fruit_grower_id', '=', self.contract_id.partner_id.id))
        orders = self.env['step.packing.production'].search(domain)
        orders._lock_process()
        return orders

    def _fruit_origin_receipts(self, output):
        """Walk native OT, split and repalletization ancestry, never dispatch guides."""
        seen = self.env['stock.quant.package']
        frontier = output
        while frontier:
            frontier.check_access('read')
            seen |= frontier
            productions = self.env['step.packing.production'].search([
                ('company_id', '=', self.company_id.id),
                ('step_packing_output_tag_ids', 'in', frontier.ids)])
            repacks = self.env['step.packing.repack.line'].search([
                ('repack_id.company_id', '=', self.company_id.id),
                ('repack_id.state', '=', 'done'), ('target_package_id', 'in', frontier.ids)])
            parents = (productions.step_packing_input_tag_ids | repacks.source_package_id
                       | frontier.step_tag_line_ids.source_package_id)
            frontier = self.env['stock.quant.package'].search([
                ('id', 'in', (parents - seen).ids),
                '|', ('company_id', '=', False), ('company_id', '=', self.company_id.id)])
        receipts = self.env['stock.picking'].search([
            ('company_id', '=', self.company_id.id), ('picking_type_code', '=', 'incoming'),
            ('state', '=', 'done'), ('fruit_tag_line_ids.package_id', 'in', seen.ids)])
        receipts |= self.env['stock.move.line'].search([
            ('company_id', '=', self.company_id.id), ('result_package_id', 'in', seen.ids),
            ('state', '=', 'done'), ('picking_id.picking_type_code', '=', 'incoming')]).picking_id
        return receipts

    def _fruit_tax_ids(self, product, subject, retention):
        taxes = product.with_company(self.company_id).supplier_taxes_id
        taxes = taxes.filtered_domain(taxes._check_company_domain(self.company_id))._filter_taxes_by_company(self.company_id)
        taxes = taxes.flatten_taxes_hierarchy().filtered(
            lambda tax: not (tax.amount_type == 'percent' and tax.amount < 0))
        return taxes | retention if subject else taxes

    def action_prepare_bills(self):
        return self._fruit_prepare()

    def _fruit_prepare(self, ignore_legacy=False, only_orders=None, reuse_draft=True):
        with self.env.cr.savepoint():
            return self._fruit_prepare_documents(ignore_legacy, only_orders, reuse_draft)

    def _fruit_prepare_documents(self, ignore_legacy=False, only_orders=None, reuse_draft=True):
        self.ensure_one()
        orders = self._fruit_orders()
        if only_orders is not None:
            if only_orders - orders:
                raise ValidationError(_('Las OT seleccionadas no corresponden a esta compra mensual.'))
            orders &= only_orders
        legacy = orders.purchase_bill_id.filtered(lambda bill: bill.state != 'cancel')
        if legacy and not ignore_legacy:
            drafts = legacy.filtered(lambda bill: bill.state == 'draft' and not bill.posted_before)
            if drafts:
                if not self.env.user.has_group('account.group_account_manager'):
                    raise UserError(_('Contabilidad debe revisar los borradores mensuales existentes antes de trasladarlos a proformas.'))
                review = self.env['step.packing.fruit.proforma.migration'].create({
                    'monthly_wizard_id': self.id, 'move_ids': [Command.set(drafts.ids)]})
                return {'type': 'ir.actions.act_window', 'res_model': review._name,
                        'res_id': review.id, 'view_mode': 'form', 'target': 'new'}
        tags = orders.step_packing_output_tag_ids.filtered(lambda tag: tag.step_packing_result == 'export')
        if tags:
            tags.check_access('write')
            self.env.cr.execute('SELECT id FROM stock_quant_package WHERE id=ANY(%s) ORDER BY id FOR UPDATE', [tags.ids])
            tags.invalidate_recordset(['step_fruit_proforma_id'])
        existing = tags.step_fruit_proforma_id.filtered(lambda quote: quote.step_fruit_state != 'cancel')
        groups = defaultdict(list)
        for production in orders.filtered(lambda row: not row.purchase_bill_id or row.purchase_bill_id.state == 'cancel'):
            contract = production.contract_id if production.valuation_snapshot else (self.contract_id or production.contract_id)
            if not contract:
                raise UserError(_('La OT %s no tiene precios de cierre. Seleccione el contrato para preparar su proforma.') % production.name)
            contract.check_access('read')
            prices = production.valuation_snapshot or production._contract_prices(contract, for_billing=True)
            for price in prices:
                tag = self.env['stock.quant.package'].browse(price['tag_id'])
                if tag not in tags:
                    raise ValidationError(_('Los precios de cierre contienen una tarja ajena a la OT.'))
                if tag.step_fruit_proforma_id and tag.step_fruit_proforma_id.step_fruit_state != 'cancel':
                    continue
                species = tag.especie_id
                subject, retention = species._fruit_vat_policy_for(self.company_id, validate=True)
                code = '46' if subject else '33'
                source = self.env['step.producer.purchase.contract.product'].browse(price['contract_line_id'])
                account = self._billing_expense_account(source)
                if not account:
                    raise UserError(_('Configure la cuenta de gastos del producto o su categoría: %s.') % source.product_id.display_name)
                product = self.env['product.product'].browse(price.get('bill_product_id', price['product_id']))
                receipts = self._fruit_origin_receipts(tag)
                guides = sorted(set(receipts.mapped('fruit_guide_number')) - {False, ''})
                row = dict(price, tag_name=tag.name, ot_name=production.name,
                           product_name=product.display_name, product_id=product.id,
                           species_name=species.display_name, variety_name=tag.variedad_id.display_name or '-',
                           uom_name=self.env['uom.uom'].browse(price['uom_id']).display_name,
                           receipt_guides=guides, variety_id=tag.variedad_id.id,
                           production_id=production.id, contract_id=contract.id,
                           expense_id=account.id, tax_ids=self._fruit_tax_ids(product, subject, retention).ids,
                           receipt_ids=receipts.ids)
                groups[(production.fruit_grower_id.id, species.id, contract.currency_id.id, code, retention.id)].append(row)
        result = existing
        warehouse = self.env['stock.warehouse'].search([('company_id', '=', self.company_id.id)], limit=1)
        if groups and not warehouse:
            raise UserError(_('La sucursal necesita una bodega configurada para identificar su operación de compras. No se generarán movimientos de stock.'))
        for (producer, species, currency, code, retention), incoming in groups.items():
            domain = [('step_fruit_proforma', '=', True), ('company_id', '=', self.company_id.id),
                      ('partner_id', '=', producer), ('currency_id', '=', currency),
                      ('step_fruit_species_id', '=', species), ('step_fruit_dte_code', '=', code),
                      ('step_fruit_withholding_tax_id', '=', retention or False),
                      ('step_fruit_period_start', '=', self.date_start), ('step_fruit_period_end', '=', self.date_end),
                      ('step_fruit_state', '=', 'draft')]
            quote = self.env['purchase.order'].search(domain, limit=1) if reuse_draft else self.env['purchase.order']
            if not quote:
                quote = self.env['purchase.order'].with_company(self.company_id).with_context(_fruit_proforma=_FRUIT).create({
                    'step_fruit_proforma': True,
                    'name': self.env['ir.sequence'].next_by_code('step.packing.fruit.proforma.' + code),
                    'partner_id': producer, 'company_id': self.company_id.id, 'currency_id': currency,
                    'picking_type_id': warehouse.in_type_id.id, 'date_order': fields.Datetime.now(),
                    'step_fruit_species_id': species, 'step_fruit_dte_code': code,
                    'step_fruit_period_start': self.date_start, 'step_fruit_period_end': self.date_end,
                    'step_fruit_withholding_tax_id': retention or False})
            quote._fruit_lock()
            all_rows = [row for line in quote.order_line for row in (line.step_fruit_source_rows or [])] + incoming
            by_variety = defaultdict(list)
            for row in all_rows:
                by_variety[row['variety_id']].append(row)
            commands = []
            for variety, rows in by_variety.items():
                dimensions = {(row['product_id'], row['uom_id'], row['expense_id'], tuple(sorted(row['tax_ids']))) for row in rows}
                if len(dimensions) != 1:
                    raise ValidationError(_('La variedad %s tiene productos, unidades, cuentas o impuestos distintos. Revise su configuración antes de resumirla en una sola línea.') % rows[0]['variety_name'])
                product, unit, expense, taxes = next(iter(dimensions))
                qty, amount = sum(row['quantity'] for row in rows), sum(row['amount'] for row in rows)
                if qty <= 0:
                    raise ValidationError(_('La cantidad resumida debe ser positiva.'))
                mapped = quote.fiscal_position_id.map_tax(self.env['account.tax'].browse(taxes))
                source_tags = self.env['stock.quant.package'].browse(list({row['tag_id'] for row in rows}))
                values = {'name': '%s / %s' % (rows[0]['species_name'], rows[0]['variety_name']),
                          'product_id': product, 'product_qty': qty, 'product_uom': unit,
                          'price_unit': amount / qty, 'discount': 0, 'date_planned': fields.Datetime.now(),
                          'taxes_id': [Command.set(mapped.ids)], 'step_fruit_variety_id': variety or False,
                          'step_fruit_expense_account_id': expense, 'step_fruit_source_rows': rows,
                          'step_fruit_contract_line_ids': [Command.set(list({row['contract_line_id'] for row in rows}))],
                          'step_fruit_tag_line_ids': [Command.set(source_tags.step_tag_line_ids.ids)]}
                old = quote.order_line.filtered(lambda line: line.step_fruit_variety_id.id == variety)
                commands.append(Command.update(old.id, values) if old else Command.create(values))
            guide_refs = sorted({guide for row in all_rows for guide in row['receipt_guides']})
            quote.with_context(_fruit_proforma=_FRUIT).write({
                'order_line': commands,
                'step_fruit_contract_ids': [Command.set(list({row['contract_id'] for row in all_rows}))],
                'step_fruit_tag_ids': [Command.set(list({row['tag_id'] for row in all_rows}))],
                'step_fruit_production_ids': [Command.set(list({row['production_id'] for row in all_rows}))],
                'step_fruit_receipt_ids': [Command.set(list({ident for row in all_rows for ident in row['receipt_ids']}))],
                'step_fruit_guide_refs': ', '.join(guide_refs)})
            expected = quote.currency_id.round(sum(row['amount'] for row in all_rows))
            if not quote.currency_id.is_zero(quote.amount_untaxed - expected):
                raise ValidationError(_('El resumen no conserva el importe original. Revise precisión e impuestos incluidos en el precio antes de aprobar.'))
            new_tags = self.env['stock.quant.package'].browse(list({row['tag_id'] for row in incoming}))
            new_tags.with_context(_fruit_proforma=_FRUIT).write({'step_fruit_proforma_id': quote.id})
            result |= quote
        if not result:
            if legacy:
                raise UserError(_('Las OT del período ya tienen facturas. Se conservan sus documentos y no se duplicará la compra.'))
            raise UserError(_('No hay fruta de exportación cerrada pendiente de proforma para el período.'))
        return result._fruit_action()
