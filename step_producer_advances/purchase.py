"""Advance documents share the native reviewed purchase/invoice lifecycle."""
from collections import defaultdict

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools import frozendict
from odoo.addons.step_packing_fruit_proforma.purchase import PurchaseOrder as FruitOrder, _controlled, _internal


def source_key(row):
    return (row['tag_line_id'], row.get('input_tag_id') or 0, row['receipt_id'])


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    step_advance_proforma = fields.Boolean('Proforma anticipo productor', readonly=True, copy=False, index=True)
    step_advance_pricelist_id = fields.Many2one('product.pricelist', string='Lista de precios', readonly=True)
    step_advance_cutoff = fields.Date('Fecha corte proceso', readonly=True)
    step_advance_net_due = fields.Date('Fecha de pago Neto', readonly=True)
    step_advance_vat_due = fields.Date('Fecha de pago IVA', readonly=True)
    step_advance_source_currency_id = fields.Many2one('res.currency', string='Moneda lista', readonly=True)
    step_advance_exchange_rate = fields.Float('Tipo de cambio', digits=(24, 12), readonly=True)
    step_advance_status = fields.Selection([
        ('draft', 'Creada'), ('approved', 'Validada'), ('prepared', 'Factura en borrador'),
        ('posted', 'Contabilizada'), ('cancel', 'Cancelada')],
        compute='_compute_advance_status', string='Estado anticipo')
    _FRUIT_SOURCE_FIELDS = FruitOrder._FRUIT_SOURCE_FIELDS | {
        'step_advance_proforma', 'step_advance_pricelist_id', 'step_advance_cutoff',
        'step_advance_net_due', 'step_advance_vat_due', 'step_advance_source_currency_id',
        'step_advance_exchange_rate',
        'step_fruit_receipt_ids',
    }

    @api.model_create_multi
    def create(self, values_list):
        for values in values_list:
            if values.get('step_advance_proforma', self.env.context.get('default_step_advance_proforma')):
                if not _internal(self) or not values.get('step_fruit_proforma'):
                    raise UserError(_('Prepare los anticipos desde su asistente de Productores.'))
        return super().create(values_list)

    def write(self, values):
        if 'step_advance_proforma' in values and any(order.step_advance_proforma != bool(values['step_advance_proforma']) for order in self):
            raise UserError(_('No cambie el tipo de una proforma existente.'))
        return super().write(values)

    @api.depends('step_fruit_state', 'invoice_ids.state')
    def _compute_advance_status(self):
        for order in self:
            state = order.step_fruit_state
            if state == 'invoiced':
                state = 'posted' if order.invoice_ids.filtered(lambda move: move.state == 'posted') else 'prepared'
            order.step_advance_status = state

    def _fruit_check_period(self):
        if not self.step_advance_proforma:
            return super()._fruit_check_period()
        if (not self.step_fruit_period_start or not self.step_fruit_period_end
                or self.step_fruit_period_end < self.step_fruit_period_start
                or not self.step_advance_cutoff or self.step_advance_cutoff < self.step_fruit_period_end
                or not self.step_advance_net_due or not self.step_advance_vat_due):
            raise ValidationError(_('Revise el período de recepción, corte de proceso y ambas fechas de pago.'))
        if self.currency_id.compare_amounts(self.amount_tax, 0) < 0:
            raise ValidationError(_('El IVA a pagar no puede producir una cuota negativa. Revise los impuestos seleccionados.'))

    def _fruit_check_tag_links(self):
        if not self.step_advance_proforma:
            return super()._fruit_check_tag_links()
        own = [row for line in self.order_line for row in (line.step_fruit_source_rows or [])]
        keys = [source_key(row) for row in own]
        if len(keys) != len(set(keys)) or {row['tag_id'] for row in own} != set(self.step_fruit_tag_ids.ids):
            raise ValidationError(_('La proforma contiene fuentes repetidas o tarjas sin detalle.'))
        if any(tag.step_fruit_proforma_id and tag.step_fruit_proforma_id.step_fruit_state != 'cancel'
               for tag in self.step_fruit_tag_ids):
            raise UserError(_('Una tarja ya pertenece a una compra mensual. Revise sus documentos antes del anticipo.'))
        others = self.env['purchase.order'].search([
            ('id', '!=', self.id), ('step_advance_proforma', '=', True),
            ('step_fruit_state', '!=', 'cancel'), ('step_fruit_tag_ids', 'in', self.step_fruit_tag_ids.ids)])
        reserved = {source_key(row) for line in others.order_line for row in (line.step_fruit_source_rows or [])}
        if set(keys) & reserved:
            raise UserError(_('Estos kilos de recepción ya están incluidos en otro anticipo activo.'))

    def _fruit_sequence_code(self, dte_code):
        return 'step.producer.advance.' + dte_code if self.step_advance_proforma else super()._fruit_sequence_code(dte_code)

    def _fruit_action(self):
        if not self or not all(self.mapped('step_advance_proforma')):
            return super()._fruit_action()
        action = self.env['ir.actions.act_window']._for_xml_id('step_producer_advances.action_advance_proformas')
        if len(self) == 1:
            action.update(res_id=self.id, view_mode='form', views=[(
                self.env.ref('step_producer_advances.advance_proforma_form').id, 'form')])
        else:
            action['domain'] = [('id', 'in', self.ids)]
        return action

    def _fruit_link_productions(self, bill):
        if not self.step_advance_proforma:
            return super()._fruit_link_productions(bill)
        # One OT can contain several receipt weeks. Its native M2M proforma
        # relation retains every advance; the single monthly bill is untouched.
        self._fruit_check_existing_production_bills(bill)

    def _prepare_invoice(self):
        values = super()._prepare_invoice()
        if self.step_advance_proforma:
            values.update(invoice_date=fields.Date.to_date(self.date_order),
                          invoice_date_due=max(self.step_advance_net_due, self.step_advance_vat_due),
                          invoice_payment_term_id=False)
        return values


class PurchaseLine(models.Model):
    _inherit = 'purchase.order.line'

    step_advance_priced_product_id = fields.Many2one('product.product', string='Producto valorizado', readonly=True)
    step_advance_market_id = fields.Many2one('step.fruit.market', string='Mercado', readonly=True)
    step_advance_packaging_id = fields.Many2one('product.packaging', string='Embalaje', readonly=True)

    def _prepare_account_move_line(self, move=False):
        values = super()._prepare_account_move_line(move)
        if self.order_id.step_advance_proforma:
            values['name'] = _('Anticipo kg - %s') % self.step_advance_priced_product_id.display_name
        return values


class Package(models.Model):
    _inherit = 'stock.quant.package'

    step_advance_market_id = fields.Many2one('step.fruit.market', string='Mercado anticipo', ondelete='restrict',
        help='Mercado comercial usado por la lista de precios del anticipo. Se conserva al preparar una proforma.')
    step_advance_proforma_ids = fields.Many2many('purchase.order', 'step_fruit_proforma_tag_rel',
        'package_id', 'order_id', string='Proformas anticipo productor', readonly=True, copy=False,
        domain=[('step_advance_proforma', '=', True)])

    def write(self, values):
        if 'step_advance_proforma_ids' in values:
            raise UserError(_('Las proformas se vinculan desde la preparación del anticipo.'))
        if 'step_advance_market_id' in values:
            self.check_access('write')
            self.flush_recordset()
            self.env.cr.execute('SELECT id FROM stock_quant_package WHERE id=ANY(%s) ORDER BY id FOR UPDATE', [self.ids])
            if self.env['purchase.order'].search_count([
                    ('step_advance_proforma', '=', True), ('step_fruit_state', '!=', 'cancel'),
                    ('step_fruit_tag_ids', 'in', self.ids)], limit=1):
                raise UserError(_('El mercado se conserva mientras la tarja tenga anticipos activos.'))
        return super().write(values)

    @api.model_create_multi
    def create(self, values_list):
        if any(values.get('step_advance_proforma_ids', self.env.context.get('default_step_advance_proforma_ids')) for values in values_list):
            raise UserError(_('Las proformas se vinculan desde la preparación del anticipo.'))
        return super().create(values_list)


class MonthlyWizard(models.TransientModel):
    _inherit = 'step.packing.monthly.fruit.bill'

    def _fruit_orders(self):
        orders = super()._fruit_orders()
        if self.env['purchase.order'].search_count([
                ('step_advance_proforma', '=', True), ('step_fruit_state', '!=', 'cancel'),
                ('step_fruit_tag_ids', 'in', orders.step_packing_output_tag_ids.ids)], limit=1):
            raise UserError(_('Hay anticipos activos sobre estas tarjas. Revise sus documentos; no se prepara otra compra mensual sobre los mismos kilos.'))
        return orders


class AccountMove(models.Model):
    _inherit = 'account.move'

    @api.depends('invoice_payment_term_id', 'invoice_date', 'currency_id', 'amount_total_in_currency_signed',
                 'invoice_date_due', 'amount_untaxed', 'amount_tax', 'step_fruit_proforma_id.step_advance_proforma',
                 'step_fruit_proforma_id.step_advance_net_due', 'step_fruit_proforma_id.step_advance_vat_due')
    def _compute_needed_terms(self):
        super()._compute_needed_terms()
        for move in self.filtered(lambda item: item.move_type == 'in_invoice' and item.step_fruit_proforma_id.step_advance_proforma):
            order = move.step_fruit_proforma_id
            if not move.needed_terms or not move.amount_total:
                continue
            total_balance = sum(value['balance'] for value in move.needed_terms.values())
            total_currency = sum(value['amount_currency'] for value in move.needed_terms.values())
            fraction = move.amount_untaxed / move.amount_total
            net_balance = move.company_currency_id.round(total_balance * fraction)
            net_currency = move.currency_id.round(total_currency * fraction)
            result = {}
            for day, balance, amount in (
                    (order.step_advance_net_due, net_balance, net_currency),
                    (order.step_advance_vat_due, total_balance - net_balance, total_currency - net_currency)):
                if move.currency_id.is_zero(amount) and move.company_currency_id.is_zero(balance):
                    continue
                key = frozendict(move_id=move.id, date_maturity=day, discount_date=False)
                value = result.setdefault(key, {'balance': 0.0, 'amount_currency': 0.0})
                value['balance'] += balance
                value['amount_currency'] += amount
            move.needed_terms = result
