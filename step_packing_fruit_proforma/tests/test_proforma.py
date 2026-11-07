"""Monthly fruit documents must retain native purchase/accounting traceability.

The closed OT fixtures represent legacy production: they deliberately perform
no manufacturing or stock transfer. Every master belongs to the test transaction;
no supplier invoice is posted and no fiscal folio or message is sent.
"""
from unittest.mock import patch

from odoo import Command
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import TransactionCase, tagged
from odoo.tests.common import new_test_user

from odoo.addons.step_packing_operations.models.contract_valuation import _VALUATION
from odoo.addons.step_packing_operations.models.process_control import _INTERNAL


from .common import FruitProformaCase


@tagged('post_install', '-at_install', 'step_packing_fruit_proforma')
class TestMonthlyFruitProforma(FruitProformaCase):
    def test_preparation_creates_purchase_proforma_without_accounting_or_stock(self):
        production, tag, source = self._case()
        before_stock = self._stock_counts()
        before_bills = self.env['account.move'].search_count([('company_id', '=', self.branch.id)])
        order = self._prepare(production)
        self.assertTrue(order.step_fruit_proforma)
        self.assertEqual(order.step_fruit_state, 'draft')
        self.assertEqual(order.state, 'draft')
        self.assertEqual(order.step_fruit_dte_code, '33')
        self.assertTrue(order.name.startswith('PF33/'))
        self.assertEqual(order.step_fruit_contract_ids, source.contract_id)
        self.assertEqual(order.step_fruit_production_ids, production)
        self.assertEqual(order.step_fruit_tag_ids, tag)
        self.assertEqual(tag.step_fruit_proforma_id, order)
        self.assertEqual(len(order.order_line), 1)
        self.assertEqual(order.order_line.step_fruit_tag_line_ids, tag.step_tag_line_ids)
        self.assertFalse(production.purchase_bill_id)
        self.assertFalse(order.invoice_ids)
        self.assertEqual(self.env['account.move'].search_count([('company_id', '=', self.branch.id)]), before_bills)
        self.assertEqual(self._stock_counts(), before_stock)

    def test_33_conversion_requires_received_invoice_and_is_native_idempotent_draft(self):
        production, tag, source = self._case()
        order = self._prepare(production)
        before_stock = self._stock_counts()
        with self.assertRaises(UserError), self.cr.savepoint():
            order.action_fruit_convert()
        self._approve(order)
        with self.assertRaises(UserError), self.cr.savepoint():
            order.action_fruit_convert()
        order.step_fruit_supplier_invoice_received = True
        with self.assertRaises(UserError), self.cr.savepoint():
            order.action_fruit_convert()
        bill = self._convert(order)
        self.assertEqual(bill.move_type, 'in_invoice')
        self.assertEqual(bill.l10n_latam_document_type_id, self.env.ref('l10n_cl.dc_a_f_dte'))
        self.assertEqual((bill.l10n_latam_document_number or '').lstrip('0'), '17101')
        self.assertEqual(bill.company_id, self.branch)
        self.assertEqual(bill.currency_id, self.branch.currency_id)
        self.assertEqual(bill.journal_id, self.journal)
        self.assertEqual(bill.invoice_line_ids.purchase_line_id, order.order_line)
        self.assertEqual(bill.invoice_line_ids.account_id, self.expense)
        self.assertEqual(bill.invoice_line_ids.product_uom_id, self.base.uom_id)
        self.assertEqual(bill.invoice_line_ids.quantity, 20)
        self.assertEqual(bill.step_fruit_proforma_id, order)
        self.assertEqual(production.purchase_bill_id, bill)
        self.assertEqual(order.step_fruit_state, 'invoiced')
        self.assertEqual(order.order_line.qty_received, 0)
        self.assertFalse(order.picking_ids)
        self.assertFalse(order.order_line.move_ids)
        self.assertEqual(bill.line_ids.filtered(lambda row: row.display_type == 'payment_term').account_id, self.payable)
        self.assertAlmostEqual(sum(bill.line_ids.mapped('balance')), 0)
        order.action_fruit_convert()
        self.assertEqual(order.invoice_ids.filtered(lambda move: move.state != 'cancel'), bill)
        self.assertEqual(self.env['account.move'].search_count([('step_fruit_proforma_id', '=', order.id)]), 1)
        self.assertEqual(self._stock_counts(), before_stock)

    def test_46_retains_vat_and_selected_retention_without_consuming_official_folio(self):
        production, tag, source = self._case(species=self.retained_species)
        order = self._prepare(production)
        self.assertTrue(order.name.startswith('PF46/'))
        self.assertEqual(order.step_fruit_dte_code, '46')
        self.assertEqual(order.order_line.taxes_id, self.vat | self.retention)
        self.assertEqual(order.amount_untaxed, 100)
        self.assertEqual(order.amount_total, 105)
        self._approve(order)
        bill = self._convert(order)
        self.assertEqual(bill.l10n_latam_document_type_id, self.env.ref('l10n_cl.dc_fc_f_dte'))
        self.assertFalse(bill.l10n_latam_document_number)
        self.assertIn(bill.name, (False, '/'))
        self.assertEqual(bill.invoice_line_ids.tax_ids, self.vat | self.retention)
        self.assertEqual(bill.amount_untaxed, 100)
        self.assertEqual(bill.amount_total, 105)
        self.assertNotEqual(order.name, bill.name)

    def test_retention_factor_is_selected_per_species_not_hardcoded(self):
        self.retained_species.with_company(self.root).step_withholding_tax_id = self.other_retention
        production, tag, source = self._case(species=self.retained_species)
        order = self._prepare(production)
        self.assertEqual(order.step_fruit_withholding_tax_id, self.other_retention)
        self.assertEqual(order.order_line.taxes_id, self.vat | self.other_retention)
        self.assertEqual(order.amount_total, 111.5)
        self._approve(order)
        self.assertEqual(self._convert(order).amount_total, 111.5)

    def test_reprepare_draft_uses_policy_saved_after_its_creation(self):
        production, tag, source = self._case()
        order = self._prepare(production)
        original_id, original_name = order.id, order.name
        before_stock = self._stock_counts()
        self.species.with_company(self.branch).write({
            'step_change_subject_vat': True, 'step_withholding_tax_id': self.retention.id})
        refreshed = self._prepare(production)
        self.assertEqual(refreshed.id, original_id)
        self.assertEqual(refreshed.step_fruit_dte_code, '46')
        self.assertTrue(refreshed.name.startswith('PF46/'))
        self.assertIn(original_name, refreshed.step_fruit_previous_references.splitlines())
        self.assertEqual(refreshed.order_line.taxes_id, self.vat | self.retention)
        self.assertEqual(refreshed.amount_untaxed, 100)
        self.assertEqual(refreshed.amount_total, 105)
        self.assertEqual(tag.step_fruit_proforma_id, refreshed)
        self.assertEqual(self._stock_counts(), before_stock)
        self.assertFalse(refreshed.invoice_ids)
        self._approve(refreshed)
        self.assertEqual(self._convert(refreshed).l10n_latam_document_type_id.code, '46')

    def test_stale_draft_cannot_be_approved_without_reviewing_updated_taxes(self):
        production, tag, source = self._case()
        order = self._prepare(production)
        self.species.with_company(self.branch).write({
            'step_change_subject_vat': True, 'step_withholding_tax_id': self.retention.id})
        with self.assertRaisesRegex(UserError, 'Actualizar impuestos'):
            self._approve(order)
        self.assertEqual(order.step_fruit_state, 'draft')
        self.assertEqual(order.step_fruit_dte_code, '33')
        order.action_fruit_refresh_taxes()
        self._approve(order)
        self.assertEqual(order.step_fruit_state, 'approved')

    def test_tax_refresh_is_idempotent_and_preserves_sources(self):
        production, tag, source = self._case()
        order = self._prepare(production)
        original_lines = order.order_line.ids
        original_quantities = order.order_line.mapped('product_qty')
        original_prices = order.order_line.mapped('price_unit')
        self.species.with_company(self.branch).write({
            'step_change_subject_vat': True, 'step_withholding_tax_id': self.retention.id})
        order.action_fruit_refresh_taxes()
        number, references = order.name, order.step_fruit_previous_references
        order.action_fruit_refresh_taxes()
        self.assertEqual((order.name, order.step_fruit_previous_references), (number, references))
        self.assertEqual(order.order_line.ids, original_lines)
        self.assertEqual(order.order_line.mapped('product_qty'), original_quantities)
        self.assertEqual(order.order_line.mapped('price_unit'), original_prices)
        self.assertEqual(order.step_fruit_tag_ids, tag)

    def test_changed_retention_refreshes_draft_without_renumbering_same_dte(self):
        production, tag, source = self._case(species=self.retained_species)
        order = self._prepare(production)
        name = order.name
        self.retained_species.with_company(self.root).step_withholding_tax_id = self.other_retention
        order.action_fruit_refresh_taxes()
        self.assertEqual(order.name, name)
        self.assertFalse(order.step_fruit_previous_references)
        self.assertEqual(order.step_fruit_withholding_tax_id, self.other_retention)
        self.assertEqual(order.amount_total, 111.5)

    def test_approved_proforma_cannot_refresh_its_snapshot(self):
        production, tag, source = self._case(species=self.retained_species)
        order = self._prepare(production)
        self._approve(order)
        self.retained_species.with_company(self.root).step_withholding_tax_id = self.other_retention
        with self.assertRaises(UserError):
            order.action_fruit_refresh_taxes()
        self.assertEqual(order.step_fruit_withholding_tax_id, self.retention)
        self.assertEqual(order.amount_total, 105)

    def test_explicit_branch_standard_policy_is_not_overridden_by_holding_retention(self):
        self.retained_species.with_company(self.branch).step_change_subject_vat = False
        production, tag, source = self._case(species=self.retained_species)
        order = self._prepare(production)
        order.action_fruit_refresh_taxes()
        self.assertEqual(order.step_fruit_dte_code, '33')
        self.assertFalse(order.step_fruit_withholding_tax_id)

    def test_ordinary_purchase_cannot_use_fruit_tax_refresh(self):
        order = self.env['purchase.order'].create(self._ordinary_values())
        with self.assertRaises(UserError):
            self._as_accountant(order).action_fruit_refresh_taxes()

    def test_two_species_keep_separate_proformas_and_bills_in_batch_conversion(self):
        ordinary, tag33, source33 = self._case()
        retained, tag46, source46 = self._case(species=self.retained_species)
        orders = self._prepare(ordinary | retained)
        self.assertEqual(len(orders), 2)
        self.assertEqual(set(orders.mapped('step_fruit_dte_code')), {'33', '46'})
        for order in orders:
            self._approve(order)
            if order.step_fruit_dte_code == '33':
                order.write({'step_fruit_supplier_invoice_received': True,
                             'step_fruit_supplier_document_number': '17102'})
        orders.action_create_invoice()
        bills = orders.invoice_ids
        self.assertEqual(len(bills), 2)
        self.assertEqual(set(bills.l10n_latam_document_type_id.mapped('code')), {'33', '46'})
        self.assertEqual(set(bills.mapped('state')), {'draft'})
        self.assertEqual(set(bills.step_fruit_proforma_id.ids), set(orders.ids))
        self.assertNotEqual(ordinary.purchase_bill_id, retained.purchase_bill_id)

    def test_one_variety_keeps_exact_weighted_price_and_total(self):
        first, tag1, source1 = self._case(kilos=600, price=2, snapshot=True)
        second, tag2, source2 = self._case(kilos=400, price=2.01)
        # Saved close prices retain their original contract even when the
        # operator supplies another contract for unpriced legacy output.
        order = self._prepare(first | second, self._wizard(contract=source2.contract_id))
        line = order.order_line
        self.assertEqual(len(line), 1)
        self.assertEqual(line.product_qty, 1000)
        self.assertAlmostEqual(line.price_unit, 2.004, places=12)
        self.assertEqual(line.price_subtotal, 2004)
        self.assertEqual(order.amount_untaxed, 2004)
        self.assertEqual(len(line.step_fruit_source_rows), 2)
        self.assertEqual(line.step_fruit_contract_line_ids, source1 | source2)
        self._approve(order)
        bill = self._convert(order)
        self.assertAlmostEqual(bill.invoice_line_ids.price_unit, 2.004, places=12)
        self.assertEqual(bill.amount_untaxed, 2004)

    def test_retry_and_overlapping_period_do_not_reassign_or_duplicate_tags(self):
        production, tag, source = self._case()
        wizard = self._wizard()
        order = self._prepare(production, wizard)
        wizard.action_prepare_bills()
        self._wizard(start='2026-11-05', end='2026-11-20').action_prepare_bills()
        self.assertEqual(tag.step_fruit_proforma_id, order)
        self.assertEqual(self.env['purchase.order'].search_count([
            ('step_fruit_proforma', '=', True), ('step_fruit_tag_ids', 'in', tag.ids)]), 1)
        self.assertEqual(len(order.order_line.step_fruit_source_rows), 1)
        self.assertEqual(order.order_line.product_qty, 20)

    def test_server_writes_cannot_approve_reprice_or_retarget_proforma(self):
        production, tag, source = self._case()
        order = self._prepare(production)
        for values in ({'step_fruit_state': 'approved'}, {'state': 'purchase'},
                       {'step_fruit_proforma': False}, {'partner_id': self.env.company.partner_id.id}):
            with self.assertRaises(UserError), self.cr.savepoint():
                order.write(values)
        for values in ({'price_unit': 1}, {'product_qty': 100}, {'taxes_id': [Command.clear()]}):
            with self.assertRaises(UserError), self.cr.savepoint():
                order.order_line.write(values)
        with self.assertRaises(UserError), self.cr.savepoint():
            tag.write({'step_fruit_proforma_id': False})
        with self.assertRaises(UserError), self.cr.savepoint():
            order.copy()
        self.assertEqual(order.step_fruit_state, 'draft')
        self.assertEqual(order.state, 'draft')
        self.assertEqual(order.order_line.price_unit, 5)
        self.assertEqual(tag.step_fruit_proforma_id, order)

    def test_pure_accountant_can_prepare_flagged_but_not_create_ordinary_purchase(self):
        production, tag, source = self._case()
        self.assertFalse(self.operator.has_group('purchase.group_purchase_user'))
        self.assertTrue(self._prepare(production).step_fruit_proforma)
        ordinary = self.env['purchase.order'].with_company(self.branch).create(self._ordinary_values())
        ordinary_line = self.env['purchase.order.line'].create(self._ordinary_line_values(ordinary))
        # Native accounting read/write flows are retained; only create is scoped.
        accountant_order = self._as_accountant(ordinary)
        self.assertEqual(accountant_order.partner_id, self.producer)
        accountant_order.write({'partner_ref': 'Native accounting reference'})
        self._as_accountant(ordinary_line).write({'price_unit': 3.21})
        self.assertEqual(ordinary_line.price_unit, 3.21)
        with self.assertRaises(AccessError), self.cr.savepoint():
            self._as_accountant(self.env['purchase.order']).create(self._ordinary_values())
        with self.assertRaises(AccessError), self.cr.savepoint():
            self._as_accountant(self.env['purchase.order.line']).create(self._ordinary_line_values(ordinary))

    def test_mixed_purchase_accounting_role_retains_ordinary_purchase_creation(self):
        buyer = new_test_user(self.env, login='fruit-proforma-buyer-test',
            groups='account.group_account_user,purchase.group_purchase_user,base.group_multi_company',
            company_id=self.branch.id, company_ids=[Command.set((self.root | self.branch).ids)])
        purchase = self.env['purchase.order'].with_user(buyer).with_context(
            allowed_company_ids=self.branch.ids).create(self._ordinary_values())
        line = self.env['purchase.order.line'].with_user(buyer).with_context(
            allowed_company_ids=self.branch.ids).create(self._ordinary_line_values(purchase))
        self.assertFalse(purchase.step_fruit_proforma)
        self.assertEqual(line.order_id, purchase)

    def test_ordinary_purchase_and_invoice_keep_product_price_rounding(self):
        precision = self.env['decimal.precision'].search([('name', '=', 'Product Price')], limit=1)
        precision.digits = 2
        ordinary = self.env['purchase.order'].with_company(self.branch).create(self._ordinary_values())
        line = self.env['purchase.order.line'].create(self._ordinary_line_values(ordinary))
        self.assertEqual(line.price_unit, 2.35)
        line.price_unit = 3.456
        self.assertEqual(line.price_unit, 3.46)
        bill = self.env['account.move'].with_company(self.branch).create({
            'move_type': 'in_invoice', 'partner_id': self.producer.id,
            'company_id': self.branch.id, 'journal_id': self.journal.id,
            'invoice_line_ids': [Command.create({
                'name': 'Ordinary invoice precision', 'product_id': self.base.id,
                'account_id': self.expense.id, 'quantity': 1, 'price_unit': 2.345,
                'tax_ids': [Command.clear()]})]})
        self.assertEqual(bill.invoice_line_ids.price_unit, 2.35)
        bill.invoice_line_ids.price_unit = 3.456
        self.assertEqual(bill.invoice_line_ids.price_unit, 3.46)
        first, tag1, source1 = self._case(kilos=600, price=2)
        second, tag2, source2 = self._case(kilos=400, price=2.01)
        proforma = self._prepare(first | second)
        self.assertAlmostEqual(proforma.order_line.price_unit, 2.004, places=12)

    def test_incompatible_account_within_same_variety_is_rejected(self):
        first, tag1, source1 = self._case(expense=self.expense)
        second, tag2, source2 = self._case(expense=self.other_expense)
        with self.assertRaises(ValidationError) as mismatch, self.cr.savepoint():
            self._wizard().action_prepare_bills()
        self.assertIn(self.variety.name, str(mismatch.exception))
        self.assertFalse((tag1 | tag2).step_fruit_proforma_id)
        self.assertFalse((first | second).purchase_bill_id)

    def test_approved_retention_snapshot_does_not_follow_later_species_change(self):
        production, tag, source = self._case(species=self.retained_species)
        order = self._prepare(production)
        self._approve(order)
        self.retained_species.with_company(self.root).step_withholding_tax_id = self.other_retention
        bill = self._convert(order)
        self.assertEqual(order.step_fruit_withholding_tax_id, self.retention)
        self.assertEqual(bill.invoice_line_ids.tax_ids, self.vat | self.retention)
        self.assertEqual(bill.amount_total, 105)

    def test_preparation_and_conversion_preserve_existing_fifo_layers_and_quantities(self):
        production, tag, source = self._case()
        quant = self.env['stock.quant'].with_company(self.branch).create({
            'product_id': self.finished.id, 'location_id': self.warehouse.lot_stock_id.id,
            'package_id': tag.id, 'quantity': 2})
        layer = self.env['stock.valuation.layer'].with_company(self.branch).create({
            'company_id': self.branch.id, 'product_id': self.finished.id,
            'description': 'Existing FIFO source, proforma regression',
            'quantity': 2, 'unit_cost': 50, 'value': 100,
            'remaining_qty': 2, 'remaining_value': 100})
        before_layer = layer.read(['quantity', 'value', 'remaining_qty', 'remaining_value'])[0]
        before_quant = quant.read(['quantity', 'reserved_quantity', 'location_id', 'package_id'])[0]
        before_stock = self._stock_counts()
        order = self._prepare(production)
        self._approve(order)
        self._convert(order)
        layer.invalidate_recordset()
        quant.invalidate_recordset()
        self.assertEqual(layer.read(['quantity', 'value', 'remaining_qty', 'remaining_value'])[0], before_layer)
        self.assertEqual(quant.read(['quantity', 'reserved_quantity', 'location_id', 'package_id'])[0], before_quant)
        self.assertEqual(self.finished.with_company(self.branch).cost_method, 'fifo')
        self.assertEqual(self._stock_counts(), before_stock)

    def test_annex_uses_original_receipt_guide_and_ignores_outbound_guide(self):
        incoming_tag = self.env['stock.quant.package'].with_company(self.branch).create({
            'name': 'QA171 original receipt tag', 'company_id': self.branch.id,
            'is_fruit_tag': True, 'step_tag_kind': 'C',
            'step_producer_id': self.producer.id, 'especie_id': self.species.id,
            'variedad_id': self.variety.id,
            'step_tag_line_ids': [Command.create({
                'producer_id': self.producer.id, 'product_id': self.finished.id,
                'quantity': 2, 'boxes': 2, 'kilos': 20})]})
        production, output, source = self._case(input_tags=incoming_tag)

        def historical_guide(picking_type, package, number):
            picking = self.env['stock.picking'].with_company(self.branch).create({
                'company_id': self.branch.id, 'partner_id': self.producer.id,
                'picking_type_id': picking_type.id,
                'location_id': picking_type.default_location_src_id.id,
                'location_dest_id': picking_type.default_location_dest_id.id,
                'fruit_guide_number': number,
                'fruit_tag_line_ids': [Command.create({
                    'tag_number': package.name, 'package_id': package.id,
                    'product_id': self.finished.id, 'quantity': 2, 'kilos': 20,
                    'variety_id': self.variety.id})]})
            # Historical document metadata only; no new transfer is validated.
            picking.write({'state': 'done'})
            return picking

        incoming = historical_guide(self.warehouse.in_type_id, incoming_tag, 'IN-QA171')
        outgoing = historical_guide(self.warehouse.out_type_id, output, 'OUT-QA171')
        order = self._prepare(production)
        self.assertEqual(order.step_fruit_receipt_ids, incoming)
        self.assertEqual(order.step_fruit_guide_refs, 'IN-QA171')
        self.assertNotIn(outgoing.fruit_guide_number, order.step_fruit_guide_refs)
        self.assertEqual(order.order_line.step_fruit_source_rows[0]['receipt_guides'], ['IN-QA171'])

    def test_legacy_monthly_draft_requires_explicit_review_before_cancellation(self):
        production, tag, source, bill = self._legacy_draft()
        before_lines = bill.invoice_line_ids.ids
        before_stock = self._stock_counts()
        wizard = self._wizard()
        review = self._legacy_review(wizard)
        self.assertEqual(review.move_ids, bill)
        self.assertEqual(bill.state, 'draft')
        self.assertFalse(bill.posted_before)
        self.assertEqual(production.purchase_bill_id, bill)
        self.assertEqual(bill.invoice_line_ids.ids, before_lines)
        self.assertFalse(tag.step_fruit_proforma_id)
        self.assertFalse(bill.step_fruit_migrated_proforma_id)
        self.assertFalse(self.env['purchase.order'].search([
            ('step_fruit_proforma', '=', True), ('step_fruit_tag_ids', 'in', tag.ids)]))
        # Opening the review again is still read-only for the legacy document.
        second = self._legacy_review(wizard)
        self.assertEqual(second.move_ids, bill)
        self.assertEqual(bill.state, 'draft')
        self.assertEqual(self._stock_counts(), before_stock)
        kept = second.action_keep_drafts()
        self.assertEqual(kept['res_model'], 'account.move')
        self.assertEqual(bill.state, 'draft')
        self.assertEqual(production.purchase_bill_id, bill)
        self.assertFalse(tag.step_fruit_proforma_id)

    def test_explicit_legacy_migration_preserves_cancelled_history_and_retries_same_proforma(self):
        production, tag, source, bill = self._legacy_draft()
        old_lines = bill.invoice_line_ids
        old_values = old_lines.read(['name', 'product_id', 'quantity', 'price_unit', 'tax_ids'])
        before_stock = self._stock_counts()
        action = self._as_accountant(bill).action_fruit_review_proforma()
        self.assertEqual(action['res_model'], 'step.packing.fruit.proforma.migration')
        review = self._as_accountant(self.env[action['res_model']].browse(action['res_id']))
        result = review.action_move_to_proforma()
        self.assertEqual(result['res_model'], 'purchase.order')
        order = tag.step_fruit_proforma_id
        self.assertTrue(order.step_fruit_proforma)
        self.assertEqual(order.step_fruit_state, 'draft')
        self.assertEqual(order.step_fruit_production_ids, production)
        self.assertEqual(bill.state, 'cancel')
        self.assertFalse(production.purchase_bill_id)
        self.assertEqual(bill.invoice_line_ids, old_lines)
        self.assertEqual(old_lines.read(['name', 'product_id', 'quantity', 'price_unit', 'tax_ids']), old_values)
        self.assertEqual(bill.step_fruit_migrated_proforma_id, order)
        self.assertEqual(bill.step_fruit_migration_proforma_ids, order)
        self.assertEqual(order.step_fruit_legacy_move_ids, bill)
        self.assertEqual(order.amount_untaxed, bill.amount_untaxed)
        self.assertEqual(order.amount_tax, bill.amount_tax)
        self.assertEqual(order.amount_total, bill.amount_total)
        retry = review.action_move_to_proforma()
        self.assertEqual(retry['res_model'], 'purchase.order')
        self.assertEqual(retry['res_id'], order.id)
        self.assertEqual(self._prepare(production), order)
        self.assertEqual(self.env['purchase.order'].search_count([
            ('step_fruit_proforma', '=', True), ('step_fruit_tag_ids', 'in', tag.ids)]), 1)
        for operation in (lambda: bill.write({'ref': 'Changed history'}),
                          bill.button_draft, bill.action_post,
                          lambda: old_lines.write({'price_unit': 6})):
            with self.assertRaises(UserError), self.cr.savepoint():
                operation()
        self.assertEqual(bill.state, 'cancel')
        self.assertEqual(self._stock_counts(), before_stock)

    def test_previously_posted_monthly_documents_are_never_migrated(self):
        production, tag, source, bill = self._legacy_draft()
        wizard = self._wizard()
        review = self._legacy_review(wizard)
        bill.flush_recordset()
        # Represent existing fiscal history without posting/signing any DTE in
        # this test. Both posted state and a reset draft's posted_before flag
        # must independently prevent migration.
        for state in ('posted', 'draft'):
            self.cr.execute('UPDATE account_move SET state=%s, posted_before=TRUE WHERE id=%s',
                            [state, bill.id])
            bill.invalidate_recordset(['state', 'posted_before', 'step_can_migrate_fruit_bill'])
            self.assertFalse(self._as_accountant(bill).step_can_migrate_fruit_bill)
            with self.assertRaises(UserError), self.cr.savepoint():
                review.action_move_to_proforma()
            with self.assertRaises(UserError), self.cr.savepoint():
                self._as_accountant(bill).action_fruit_review_proforma()
            with self.assertRaises(UserError), self.cr.savepoint():
                wizard.action_prepare_bills()
            self.assertEqual(bill.state, state)
            self.assertEqual(production.purchase_bill_id, bill)
            self.assertFalse(tag.step_fruit_proforma_id)
            self.assertFalse(bill.step_fruit_migrated_proforma_id)

    def test_legacy_migration_amount_mismatch_rolls_back_entire_migration(self):
        self._assert_legacy_migration_rollback(price=6)

    def test_legacy_migration_tax_mismatch_rolls_back_entire_migration(self):
        self._assert_legacy_migration_rollback(taxes=self.vat | self.retention)

    def test_monthly_retry_after_conversion_returns_existing_proforma_without_legacy_review(self):
        production, tag, source = self._case()
        wizard = self._wizard()
        order = self._prepare(production, wizard)
        self._approve(order)
        bill = self._convert(order)
        reviews = self.env['step.packing.fruit.proforma.migration'].search_count([
            ('monthly_wizard_id', '=', wizard.id)])
        for retry_wizard in (wizard, self._wizard()):
            action = retry_wizard.action_prepare_bills()
            self.assertEqual(action['res_model'], 'purchase.order')
            self.assertEqual(action['res_id'], order.id)
        self.assertEqual(self.env['step.packing.fruit.proforma.migration'].search_count([
            ('monthly_wizard_id', '=', wizard.id)]), reviews)
        self.assertEqual(production.purchase_bill_id, bill)
        self.assertEqual(tag.step_fruit_proforma_id, order)
        self.assertEqual(bill.state, 'draft')
        self.assertEqual(len(order.invoice_ids), 1)

    def test_fresh_invoice_total_mismatch_rolls_back_whole_selected_batch(self):
        production33, tag33, source33 = self._case()
        production46, tag46, source46 = self._case(species=self.retained_species)
        orders = self._prepare(production33 | production46).sorted('id')
        for order in orders:
            self._approve(order)
            self.assertEqual(order.step_fruit_approved_untaxed, order.amount_untaxed)
            self.assertEqual(order.step_fruit_approved_tax, order.amount_tax)
            self.assertEqual(order.step_fruit_approved_total, order.amount_total)
            if order.step_fruit_dte_code == '33':
                order.write({'step_fruit_supplier_invoice_received': True,
                             'step_fruit_supplier_document_number': '17197'})
        failing = orders[-1]
        before_bills = self.env['account.move'].search_count([('company_id', '=', self.branch.id)])
        before_stock = self._stock_counts()
        line_type = type(self.env['purchase.order.line'])
        native_prepare = line_type._prepare_account_move_line

        def changed_native_price(line, move=False):
            values = native_prepare(line, move=move)
            if line.order_id == failing:
                values['price_unit'] += 1
            return values

        # A native invoice preparation difference in the last document must
        # also undo the first successfully prepared draft in this batch.
        with patch.object(line_type, '_prepare_account_move_line', changed_native_price):
            with self.assertRaises(UserError):
                orders.action_create_invoice()
        orders.invalidate_recordset()
        (production33 | production46).invalidate_recordset()
        self.assertFalse(orders.invoice_ids)
        self.assertFalse((production33 | production46).purchase_bill_id)
        self.assertEqual(set(orders.mapped('step_fruit_state')), {'approved'})
        self.assertEqual(self.env['account.move'].search_count([
            ('company_id', '=', self.branch.id)]), before_bills)
        self.assertEqual(self._stock_counts(), before_stock)
        with self.assertRaises(UserError), self.cr.savepoint():
            failing.write({'step_fruit_approved_total': failing.amount_total + 1})

    def test_editable_native_draft_retry_returns_existing_bill_without_repricing(self):
        production, tag, source = self._case()
        order = self._prepare(production)
        self._approve(order)
        bill = self._convert(order)
        original = order.step_fruit_approved_untaxed
        # The result is a native editable supplier bill. A later accountant's
        # change must neither regenerate nor force it back to source amounts.
        bill.invoice_line_ids.write({'price_unit': 6})
        self.assertNotEqual(bill.amount_untaxed, original)
        order.action_fruit_convert()
        self.assertEqual(order.invoice_ids.filtered(lambda move: move.state != 'cancel'), bill)
        self.assertEqual(bill.invoice_line_ids.price_unit, 6)
        self.assertEqual(order.order_line.price_unit, 5)
        self.assertEqual(order.step_fruit_approved_untaxed, original)
        self.assertEqual(production.purchase_bill_id, bill)
        self.assertEqual(self.env['account.move'].search_count([
            ('step_fruit_proforma_id', '=', order.id)]), 1)
