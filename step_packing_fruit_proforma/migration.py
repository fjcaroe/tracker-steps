"""Explicitly review old, never-posted monthly drafts before moving the cycle."""
import calendar
from collections import defaultdict

from odoo import api, Command, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.addons.step_packing_operations.models.contract_valuation import _VALUATION
from odoo.addons.step_packing_operations.models.process_control import _INTERNAL

from .guards import _FRUIT


class Move(models.Model):
    _inherit = 'account.move'

    step_fruit_origin_order_ids = fields.One2many(
        'step.packing.production', 'purchase_bill_id', string='OT de fruta',
        groups='stock.group_stock_user', readonly=True)
    step_fruit_migration_proforma_ids = fields.Many2many(
        'purchase.order', 'step_fruit_proforma_legacy_move_rel', 'move_id', 'order_id',
        string='Proformas de destino', readonly=True, copy=False)

    step_can_migrate_fruit_bill = fields.Boolean(compute='_compute_can_migrate_fruit_bill')

    @api.depends('state', 'posted_before')
    @api.depends_context('uid')
    def _compute_can_migrate_fruit_bill(self):
        permitted = self.env.user.has_group('account.group_account_manager') and self.env.user.has_group('stock.group_stock_user')
        for move in self:
            move.step_can_migrate_fruit_bill = bool(permitted and move.state == 'draft' and not move.posted_before
                and move.move_type == 'in_invoice' and move.step_fruit_origin_order_ids)

    def write(self, values):
        frozen = {'line_ids', 'invoice_line_ids', 'partner_id', 'currency_id', 'company_id', 'journal_id',
                  'date', 'invoice_date', 'name', 'ref', 'l10n_latam_document_type_id',
                  'l10n_latam_document_number', 'amount_untaxed', 'amount_tax', 'amount_total', 'auto_post'}
        if any(move.step_fruit_migrated_proforma_id for move in self) and frozen.intersection(values):
            raise UserError(_('El borrador anterior cancelado se conserva íntegro como historial de la proforma.'))
        if 'step_fruit_migration_proforma_ids' in values and self.env.context.get('_fruit_proforma') is not _FRUIT:
            raise UserError(_('Los vínculos históricos se conservan desde el traslado a proforma.'))
        return super().write(values)

    def action_fruit_review_proforma(self):
        self.ensure_one()
        if not self.env.user.has_group('account.group_account_manager'):
            raise UserError(_('El traslado requiere un responsable de Contabilidad.'))
        orders = self.step_fruit_origin_order_ids
        if not orders or self.state != 'draft' or self.posted_before or self.move_type != 'in_invoice':
            raise UserError(_('Solo se trasladan borradores mensuales de fruta que nunca fueron contabilizados.'))
        months = {order.date.strftime('%Y-%m') for order in orders}
        if len(months) != 1 or len(orders.company_id) != 1:
            raise ValidationError(_('El borrador debe corresponder a una sucursal y a un mismo mes.'))
        first = orders[:1].date.replace(day=1)
        last = first.replace(day=calendar.monthrange(first.year, first.month)[1])
        contracts = orders.contract_id
        if not contracts:
            contracts = self.env['step.producer.purchase.contract'].search([
                ('partner_id', '=', self.partner_id.id), ('company_id', 'parent_of', self.company_id.id),
                ('state', '=', 'confirmed'), ('is_superseded', '=', False),
                '|', ('date_start', '=', False), ('date_start', '<=', orders[:1].date),
                '|', ('date_end', '=', False), ('date_end', '>=', orders[:1].date)], limit=2)
        wizard = self.env['step.packing.monthly.fruit.bill'].create({
            'company_id': self.company_id.id, 'date_start': first, 'date_end': last,
            'producer_ids': [Command.set(self.partner_id.ids)],
            'contract_id': contracts.id if len(contracts) == 1 else False})
        return wizard.action_prepare_bills()


class Review(models.TransientModel):
    _name = 'step.packing.fruit.proforma.migration'
    _description = 'Revisión de borradores mensuales anteriores'

    monthly_wizard_id = fields.Many2one('step.packing.monthly.fruit.bill', required=True, readonly=True)
    company_id = fields.Many2one(related='monthly_wizard_id.company_id')
    move_ids = fields.Many2many('account.move', string='Borradores anteriores', readonly=True, required=True)

    def action_keep_drafts(self):
        self.ensure_one()
        return self.monthly_wizard_id._fruit_prepare(ignore_legacy=True)

    def action_move_to_proforma(self):
        self.ensure_one()
        if not self.env.user.has_group('account.group_account_manager'):
            raise UserError(_('El traslado requiere un responsable de Contabilidad.'))
        wizard = self.monthly_wizard_id
        orders = wizard._fruit_orders()
        moves = self.move_ids
        moves.check_access('write')
        if not moves or moves.company_id != wizard.company_id:
            raise ValidationError(_('Seleccione borradores de la sucursal del proceso.'))
        if all(move.state == 'cancel' and move.step_fruit_migrated_proforma_id for move in moves):
            return moves.step_fruit_migration_proforma_ids._fruit_action()
        all_orders = self.env['step.packing.production'].search([('purchase_bill_id', 'in', moves.ids)])
        if all_orders - orders:
            raise ValidationError(_('Un borrador incluye OT fuera del período o de los productores seleccionados. Revise el alcance completo antes de trasladarlo.'))
        if not all_orders or any(not all_orders.filtered(lambda row: row.purchase_bill_id == move) for move in moves if move.state != 'cancel'):
            raise ValidationError(_('Cada borrador debe estar vinculado a las OT mensuales del proceso.'))
        all_orders._lock_process()
        self.env.cr.execute('SELECT id FROM account_move WHERE id=ANY(%s) ORDER BY id FOR UPDATE', [moves.ids])
        moves.invalidate_recordset()
        migrated = moves.step_fruit_migration_proforma_ids
        if all(move.state == 'cancel' and move.step_fruit_migrated_proforma_id for move in moves):
            return migrated._fruit_action()
        if any(move.state != 'draft' or move.posted_before or move.move_type != 'in_invoice' for move in moves):
            raise UserError(_('Solo se trasladan borradores de proveedor que nunca fueron contabilizados. Se conservan las facturas emitidas y sus asientos.'))
        expected = defaultdict(lambda: [0.0, 0.0, 0.0])
        sources = {}
        for move in moves:
            key = (move.partner_id.id, move.currency_id.id)
            expected[key] = [a + b for a, b in zip(expected[key],
                (move.amount_untaxed, move.amount_tax, move.amount_total))]
            sources[move.id] = all_orders.filtered(lambda row: row.purchase_bill_id == move)
        with self.env.cr.savepoint():
            moves.with_context(tracking_disable=True, mail_notrack=True, mail_notify_force_send=False).button_cancel()
            all_orders.with_context(_packing_valuation=_VALUATION, _packing_control=_INTERNAL).write({'purchase_bill_id': False})
            action = wizard._fruit_prepare(ignore_legacy=True, only_orders=all_orders, reuse_draft=False)
            quotes = all_orders.step_packing_output_tag_ids.step_fruit_proforma_id.filtered(
                lambda quote: quote.step_fruit_proforma and quote.step_fruit_state != 'cancel')
            actual = defaultdict(lambda: [0.0, 0.0, 0.0])
            for quote in quotes:
                key = (quote.partner_id.id, quote.currency_id.id)
                actual[key] = [a + b for a, b in zip(actual[key],
                    (quote.amount_untaxed, quote.amount_tax, quote.amount_total))]
            if set(actual) != set(expected) or any(
                    not self.env['res.currency'].browse(key[1]).is_zero(a - b)
                    for key in expected for a, b in zip(actual[key], expected[key])):
                raise ValidationError(_('La proforma no conserva los importes del borrador anterior. Revise el contrato, Cambio sujeto IVA y Retención de la especie. No se trasladó ningún documento.'))
            for move in moves:
                destinations = quotes.filtered(lambda quote: bool(quote.step_fruit_production_ids & sources[move.id]))
                if not destinations:
                    raise ValidationError(_('Cada borrador debe conservar sus OT y su proforma de destino.'))
                destinations.with_context(_fruit_proforma=_FRUIT).write({
                    'step_fruit_legacy_move_ids': [Command.link(move.id)]})
                move.with_context(_fruit_proforma=_FRUIT).write({'step_fruit_migrated_proforma_id': destinations[:1].id})
            return action
