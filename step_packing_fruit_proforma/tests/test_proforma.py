"""Monthly fruit documents must retain native purchase/accounting traceability.

The closed OT fixtures represent legacy production: they deliberately perform
no manufacturing or stock transfer. Every master belongs to the test transaction;
no supplier invoice is posted and no fiscal folio or message is sent.
"""
from odoo import Command
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import TransactionCase, tagged
from odoo.tests.common import new_test_user

from odoo.addons.step_packing_operations.models.contract_valuation import _VALUATION
from odoo.addons.step_packing_operations.models.process_control import _INTERNAL


@tagged('post_install', '-at_install', 'step_packing_fruit_proforma')
class TestMonthlyFruitProforma(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        usd = cls.env.ref('base.USD')
        usd.active = True
        cls.root = cls.env['res.company'].create({
            'name': 'Fruit proforma test holding', 'currency_id': usd.id,
            'country_id': cls.env.ref('base.cl').id})
        cls.branch = cls.env['res.company'].create({
            'name': 'Fruit proforma test branch', 'parent_id': cls.root.id,
            'currency_id': usd.id, 'country_id': cls.env.ref('base.cl').id})
        cls.env.user.company_ids |= cls.root | cls.branch
        cls.producer = cls.env['res.partner'].create({
            'name': 'Fruit proforma test producer', 'is_productor': True,
            'country_id': cls.env.ref('base.cl').id, 'vat': 'CL11111111-1',
            'l10n_cl_sii_taxpayer_type': '1'})

        def account(code, name, kind='expense'):
            return cls.env['account.account'].with_company(cls.root).create({
                'name': name, 'code': code, 'account_type': kind,
                'reconcile': kind == 'liability_payable',
                'company_ids': [Command.set(cls.root.ids)]})

        cls.expense = account('QA171EXP', 'Fruit proforma test expense')
        cls.other_expense = account('QA171ALT', 'Fruit proforma alternative expense')
        cls.payable = account('QA171PAY', 'Fruit proforma test payable', 'liability_payable')
        cls.producer.with_company(cls.branch).property_account_payable_id = cls.payable

        def tax(name, rate):
            return cls.env['account.tax'].with_company(cls.root).create({
                'name': name, 'amount': rate, 'amount_type': 'percent',
                'type_tax_use': 'purchase', 'company_id': cls.root.id})

        cls.vat = tax('Fruit proforma test VAT', 19)
        cls.retention = tax('Fruit proforma selected retention', -14)
        cls.other_retention = tax('Fruit proforma different retention', -7.5)
        cls.species = cls.env['step.especie'].create({
            'name': 'Fruit proforma ordinary species', 'type_especie': 'frutal',
            'group_especie': 'fruta_h'})
        cls.retained_species = cls.env['step.especie'].create({
            'name': 'Fruit proforma retained species', 'type_especie': 'frutal',
            'group_especie': 'fruta_h'})
        cls.species.with_company(cls.root).write({'step_change_subject_vat': False})
        cls.retained_species.with_company(cls.root).write({
            'step_change_subject_vat': True, 'step_withholding_tax_id': cls.retention.id})
        cls.variety = cls._new_variety(cls.species, 'QA171-A')
        cls.retained_variety = cls._new_variety(cls.retained_species, 'QA171-B')
        cls.category = cls.env['product.category'].with_company(cls.branch).create({
            'name': 'Fruit proforma test category', 'property_cost_method': 'fifo',
            'property_account_expense_categ_id': cls.expense.id})
        cls.base = cls.env['product.product'].with_company(cls.branch).create({
            'name': 'Fruit proforma base kilograms', 'purchase_ok': True,
            'step_export_enabled': True, 'categ_id': cls.category.id,
            'uom_id': cls.env.ref('uom.product_uom_kgm').id,
            'uom_po_id': cls.env.ref('uom.product_uom_kgm').id,
            'property_account_expense_id': cls.expense.id,
            'supplier_taxes_id': [Command.set(cls.vat.ids)]})
        cls.finished = cls.env['product.product'].with_company(cls.branch).create({
            'name': 'Fruit proforma export carton', 'weight': 10,
            'is_storable': True, 'categ_id': cls.category.id,
            'step_export_enabled': True,
            'step_export_base_product_id': cls.base.product_tmpl_id.id})
        cls.warehouse = cls.env['stock.warehouse'].search([
            ('company_id', '=', cls.branch.id)], limit=1)
        if not cls.warehouse:
            cls.warehouse = cls.env['stock.warehouse'].create({
                'name': 'Fruit proforma test warehouse', 'code': 'Q171',
                'company_id': cls.branch.id})
        cls.journal = cls.env['account.journal'].with_company(cls.branch).create({
            'name': 'Fruit proforma test purchases', 'code': 'Q171P',
            'type': 'purchase', 'company_id': cls.branch.id,
            'default_account_id': cls.expense.id, 'l10n_latam_use_documents': True})
        cls.branch.step_packing_purchase_journal_id = cls.journal
        cls.operator = new_test_user(
            cls.env, login='fruit-proforma-accountant-test',
            groups='account.group_account_manager,stock.group_stock_manager,base.group_multi_company',
            company_id=cls.branch.id,
            company_ids=[Command.set((cls.root | cls.branch).ids)])
        # This is essential: a purchase role would mask an overbroad ACL/rule.
        if cls.operator.has_group('purchase.group_purchase_user'):
            raise AssertionError('The accountant fixture must not have a purchase role')

    @classmethod
    def _new_variety(cls, species, code):
        group = cls.env['step.grupo.variedad'].create({
            'name': code + ' group', 'especie_id': species.id})
        return cls.env['step.variedad'].create({
            'name': code, 'cod_variedad': code, 'especie_id': species.id,
            'grupo_variedad_id': group.id})

    def _as_accountant(self, records):
        return records.with_user(self.operator).with_context(allowed_company_ids=self.branch.ids)

    def _case(self, *, kilos=20, price=5, species=None, variety=None,
              expense=None, date='2026-11-09', input_tags=None, snapshot=False):
        species = species or self.species
        variety = variety or (self.retained_variety if species == self.retained_species else self.variety)
        contract = self.env['step.producer.purchase.contract'].with_company(self.root).create({
            'company_id': self.root.id, 'partner_id': self.producer.id,
            'currency_id': self.branch.currency_id.id})
        source = self.env['step.producer.purchase.contract.product'].create({
            'contract_id': contract.id, 'product_id': self.base.id,
            'species_id': species.id, 'variety_id': variety.id,
            'quantity': kilos, 'uom_id': self.base.uom_id.id, 'price_unit': price,
            'debit_account_id': expense.id if expense else False})
        self.env['step.producer.purchase.contract.installment'].create({
            'contract_id': contract.id, 'product_line_id': source.id,
            'quantity': kilos, 'date_due': '2026-11-30'})
        contract.action_confirm()
        tag = self.env['stock.quant.package'].with_company(self.branch).create({
            'name': 'QA171 output %s' % contract.id, 'company_id': self.branch.id,
            'is_fruit_tag': True, 'step_tag_kind': 'E', 'step_packing_result': 'export',
            'fruit_type': 'conventional', 'step_producer_id': self.producer.id,
            'especie_id': species.id, 'variedad_id': variety.id,
            'step_tag_line_ids': [Command.create({
                'producer_id': self.producer.id, 'product_id': self.finished.id,
                'quantity': kilos / 10, 'boxes': kilos / 10, 'kilos': kilos})]})
        production = self.env['step.packing.production'].with_company(self.branch).create({
            'company_id': self.branch.id, 'date': date,
            'fruit_grower_id': self.producer.id, 'fruit_species_id': species.id,
            'fruit_variety_id': variety.id, 'contract_id': contract.id,
            'product_id': self.finished.id, 'product_uom_id': self.finished.uom_id.id,
            'step_packing_input_tag_ids': [Command.set((input_tags or self.env['stock.quant.package']).ids)],
            'step_packing_output_tag_ids': [Command.set(tag.ids)]})
        if snapshot:
            prices = production._contract_prices(for_billing=True)
            production.with_context(_packing_valuation=_VALUATION).write({'valuation_snapshot': prices})
        production.with_context(_packing_control=_INTERNAL).write({'state': 'closed'})
        return production, tag, source

    def _wizard(self, *, start='2026-11-01', end='2026-11-30', contract=None):
        return self._as_accountant(self.env['step.packing.monthly.fruit.bill']).create({
            'company_id': self.branch.id, 'date_start': start, 'date_end': end,
            'producer_ids': [Command.set(self.producer.ids)],
            'contract_id': contract.id if contract else False})

    def _prepare(self, productions, wizard=None):
        action = (wizard or self._wizard()).action_prepare_bills()
        self.assertEqual(action['res_model'], 'purchase.order')
        orders = self.env['purchase.order'].search([
            ('step_fruit_proforma', '=', True), ('company_id', '=', self.branch.id),
            ('step_fruit_production_ids', 'in', productions.ids)])
        self.assertTrue(orders)
        return self._as_accountant(orders)

    def _approve(self, order):
        order.write({'step_fruit_approval_reference': 'QA approval'})
        order.action_fruit_approve()
        self.assertEqual(order.step_fruit_state, 'approved')
        self.assertEqual(order.state, 'purchase')

    def _convert(self, order):
        if order.step_fruit_dte_code == '33':
            order.write({'step_fruit_supplier_invoice_received': True,
                         'step_fruit_supplier_document_number': '17101'})
        order.action_fruit_convert()
        bill = order.invoice_ids.filtered(lambda move: move.state != 'cancel')
        self.assertEqual(len(bill), 1)
        self.assertEqual(bill.state, 'draft')
        return bill

    def _stock_counts(self):
        return tuple(self.env[model].search_count([('company_id', '=', self.branch.id)])
                     for model in ('stock.picking', 'stock.move', 'stock.valuation.layer'))

    def _ordinary_values(self):
        return {'partner_id': self.producer.id, 'company_id': self.branch.id,
                'currency_id': self.branch.currency_id.id,
                'picking_type_id': self.warehouse.in_type_id.id}

    def _ordinary_line_values(self, order, price=2.345):
        return {'order_id': order.id, 'product_id': self.base.id,
                'name': self.base.name, 'product_qty': 1,
                'product_uom': self.base.uom_id.id, 'price_unit': price,
                'date_planned': '2026-11-30', 'taxes_id': [Command.clear()]}

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
        self.assertEqual(bill.name, '/')
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
