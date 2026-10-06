"""Contract-priced export output and monthly draft supplier bills."""
from collections import defaultdict

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

from .process_control import _INTERNAL

_VALUATION = object()


class FruitCategory(models.Model):
    _inherit = 'step.management.fruit.category'
    step_contract_category_id = fields.Many2one('step.packing.fruit.category', string='Categoría en contratos', check_company=True)


class FruitCaliber(models.Model):
    _inherit = 'step.management.fruit.caliber'
    step_contract_caliber_id = fields.Many2one('step.packing.fruit.caliber', string='Calibre en contratos', check_company=True)
    step_2j_plus = fields.Boolean('Pertenece a 2J+')


class PackingCompany(models.Model):
    _inherit = 'res.company'
    step_packing_require_contract = fields.Boolean('Exigir contrato para fruta de exportación')
    step_packing_purchase_journal_id = fields.Many2one('account.journal', string='Diario compra fruta exportación', check_company=True, domain="[('type','=','purchase')]")

    @api.constrains('step_packing_purchase_journal_id')
    def _check_packing_journal(self):
        for company in self:
            journal = company.step_packing_purchase_journal_id
            if journal and (journal.company_id != company or journal.type != 'purchase'):
                raise ValidationError(_('El diario debe ser de compras y de la misma empresa.'))


class PackingProduction(models.Model):
    _inherit = 'step.packing.production'
    contract_id = fields.Many2one('step.producer.purchase.contract', string='Contrato compra fruta', check_company=True)
    valuation_snapshot = fields.Json('Precios de cierre', copy=False, readonly=True)
    contract_currency_id = fields.Many2one(related='contract_id.currency_id')
    contract_amount = fields.Monetary('Fruta exportación según contrato', currency_field='contract_currency_id', compute='_compute_contract_amount')
    purchase_bill_id = fields.Many2one('account.move', string='Factura mensual productor', readonly=True, copy=False)

    @api.depends('valuation_snapshot')
    def _compute_contract_amount(self):
        for record in self:
            record.contract_amount = sum(row['amount'] for row in (record.valuation_snapshot or []))

    def _contract_prices(self):
        self.ensure_one()
        tags = self.step_packing_output_tag_ids.filtered(lambda tag: tag.step_packing_result == 'export')
        if not tags:
            return []
        contract = self.contract_id
        if not contract:
            if self.company_id.step_packing_require_contract:
                raise UserError(_('Seleccione el contrato de compra para valorizar la fruta de exportación.'))
            return []
        if (contract.company_id != self.company_id or contract.partner_id != self.fruit_grower_id or
            contract.state != 'confirmed' or contract.is_superseded or
            contract.date_start and self.date < contract.date_start or contract.date_end and self.date > contract.date_end):
            raise UserError(_('Use un contrato vigente, confirmado y de este productor y empresa.'))
        result = []
        for tag in tags:
            for detail in tag.step_tag_line_ids:
                candidates = contract.product_line_ids.filtered(lambda row: row.product_id == detail.product_id and row.species_id == tag.especie_id)
                category = tag.fruit_category_id.step_contract_category_id
                caliber = tag.fruit_caliber_id.step_contract_caliber_id
                if (tag.fruit_category_id and not category and any(row.category_id for row in candidates) or
                    tag.fruit_caliber_id and not caliber and any(row.caliber_id for row in candidates)):
                    raise UserError(_('Vincule la categoría y el calibre de Inventario con sus equivalentes en contratos.'))
                price = self.env['step.producer.purchase.contract.product'].resolve_variant_price(
                    contract, detail.product_id, tag.especie_id, tag.variedad_id, category, caliber)
                product = detail.product_id.with_company(self.company_id)
                if product.cost_method == 'standard':
                    raise UserError(_('La valorización contractual requiere costo promedio o FIFO para %s.') % product.display_name)
                quantity = product.uom_id._compute_quantity(detail.quantity, price.uom_id)
                amount = quantity * price.price_unit
                company_amount = contract.currency_id._convert(amount, self.company_id.currency_id, self.company_id, self.date, round=False)
                result.append({'tag_id': tag.id, 'product_id': product.id, 'contract_line_id': price.id,
                    'quantity': quantity, 'uom_id': price.uom_id.id, 'price_unit': price.price_unit,
                    'amount': amount, 'stock_quantity': detail.quantity, 'company_amount': company_amount})
        return result

    def action_step_packing_close(self):
        self._lock_process()
        with self.env.cr.savepoint():
            for record in self:
                prices = record._contract_prices()
                record.with_context(_packing_valuation=_VALUATION).write({'valuation_snapshot': prices})
                super(PackingProduction, record).action_step_packing_close()
        return True

    def _packing_move_extra_values(self, product, qty, source, dest, lines):
        values = super()._packing_move_extra_values(product, qty, source, dest, lines)
        rows = [row for row in (self.valuation_snapshot or []) if row['product_id'] == product.id]
        if source.usage == 'production' and dest.usage == 'internal' and rows:
            # National output remains producer-owned and is excluded from valuation.
            owned = [line for line in lines if line[0] == product and len(line) == 6 and line[5]]
            if owned:
                raise UserError(_('Use productos distintos para fruta de exportación y fruta nacional.'))
            values.update({'price_unit': sum(row['company_amount'] for row in rows) / sum(row['stock_quantity'] for row in rows),
                           'step_packing_contract_valued': True})
        return values

    @api.model_create_multi
    def create(self, vals_list):
        if any(row.get('valuation_snapshot') or row.get('purchase_bill_id') for row in vals_list):
            raise UserError(_('Los precios y la factura se generan desde las acciones de Packing.'))
        return super().create(vals_list)

    def write(self, vals):
        internal = self.env.context.get('_packing_valuation') is _VALUATION
        if {'valuation_snapshot', 'purchase_bill_id'} & vals.keys() and not internal:
            raise UserError(_('Los precios y la factura se generan desde las acciones de Packing.'))
        if 'contract_id' in vals and any(row.state != 'created' or row.material_review_state == 'approved' for row in self):
            raise UserError(_('Seleccione el contrato antes de validar la OT.'))
        return super().write(vals)


class StockMove(models.Model):
    _inherit = 'stock.move'
    step_packing_contract_valued = fields.Boolean(copy=False, readonly=True)

    def _should_force_price_unit(self):
        return self.step_packing_contract_valued or super()._should_force_price_unit()


class MonthlyFruitBill(models.TransientModel):
    _name = 'step.packing.monthly.fruit.bill'
    _description = 'Preparar facturas mensuales de fruta de exportación'
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    date_start = fields.Date('Desde', required=True)
    date_end = fields.Date('Hasta', required=True)
    producer_ids = fields.Many2many('res.partner', string='Productores', domain="[('is_productor','=',True)]")

    def action_prepare_bills(self):
        self.ensure_one()
        if not self.env.user.has_group('account.group_account_user'):
            raise UserError(_('La preparación de facturas requiere permisos de Contabilidad.'))
        if self.company_id not in self.env.companies or self.date_end < self.date_start or self.date_start.strftime('%Y-%m') != self.date_end.strftime('%Y-%m'):
            raise ValidationError(_('Seleccione una empresa habilitada y un período dentro del mismo mes.'))
        journal = self.company_id.step_packing_purchase_journal_id
        if not journal:
            raise UserError(_('Configure el diario Compra fruta exportación en los parámetros contables.'))
        domain = [('company_id', '=', self.company_id.id), ('state', 'in', ['closed', 'costed', 'accounted']),
                  ('date', '>=', self.date_start), ('date', '<=', self.date_end), ('contract_id', '!=', False)]
        if self.producer_ids:
            domain.append(('fruit_grower_id', 'in', self.producer_ids.ids))
        productions = self.env['step.packing.production'].search(domain)
        productions._lock_process()
        grouped = defaultdict(lambda: self.env['step.packing.production'])
        bills = productions.mapped('purchase_bill_id')
        for record in productions.filtered(lambda row: not row.purchase_bill_id and row.valuation_snapshot):
            grouped[record.fruit_grower_id.id, record.contract_id.currency_id.id] |= record
        with self.env.cr.savepoint():
            for (producer_id, currency_id), group in grouped.items():
                lines = []
                for record in group:
                    for row in record.valuation_snapshot:
                        source = self.env['step.producer.purchase.contract.product'].browse(row['contract_line_id'])
                        if not source.debit_account_id:
                            raise UserError(_('Configure la cuenta de cargo en cada producto del contrato.'))
                        taxes = source.product_id.supplier_taxes_id.filtered(lambda tax: tax.company_id == self.company_id)
                        lines.append((0, 0, {'name': '%s / tarja %s / %s' % (record.name, row['tag_id'], source.contract_id.name),
                            'product_id': row['product_id'], 'product_uom_id': row['uom_id'], 'quantity': row['quantity'],
                            'price_unit': row['price_unit'], 'account_id': source.debit_account_id.id,
                            'analytic_distribution': source.analytic_distribution, 'tax_ids': [(6, 0, taxes.ids)]}))
                bill = self.env['account.move'].with_company(self.company_id).create({
                    'move_type': 'in_invoice', 'partner_id': producer_id, 'company_id': self.company_id.id,
                    'currency_id': currency_id, 'journal_id': journal.id, 'invoice_date': self.date_end,
                    'invoice_origin': ', '.join(group.mapped('name')), 'invoice_line_ids': lines})
                group.with_context(_packing_valuation=_VALUATION, _packing_control=_INTERNAL).write({'purchase_bill_id': bill.id})
                bills |= bill
        if not bills:
            raise UserError(_('No hay fruta contractual cerrada para el período.'))
        return {'type': 'ir.actions.act_window', 'res_model': 'account.move', 'view_mode': 'list,form', 'domain': [('id', 'in', bills.ids)]}
