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


class FruitProformaCase(TransactionCase):
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
        # This isolated holding has no chart/template tax groups. Supply the
        # native mandatory relation rather than relying on demo/chart defaults.
        cls.tax_group = cls.env['account.tax.group'].with_company(cls.root).create({
            'name': 'Fruit proforma test taxes', 'company_id': cls.root.id,
            'country_id': cls.env.ref('base.cl').id})

        def tax(name, rate):
            return cls.env['account.tax'].with_company(cls.root).create({
                'name': name, 'amount': rate, 'amount_type': 'percent',
                'type_tax_use': 'purchase', 'company_id': cls.root.id,
                'tax_group_id': cls.tax_group.id})

        cls.vat = tax('Fruit proforma test VAT', 19)
        cls.retention = tax('Fruit proforma selected retention', -14)
        cls.other_retention = tax('Fruit proforma different retention', -7.5)
        cls.species = cls.env['step.especie'].create({
            'name': 'Fruit proforma ordinary species', 'type_especie': 'frutal',
            'group_especie': 'fruta_h', 'company_id': cls.root.id,
            'company_ids': [Command.set((cls.root | cls.branch).ids)]})
        cls.retained_species = cls.env['step.especie'].create({
            'name': 'Fruit proforma retained species', 'type_especie': 'frutal',
            'group_especie': 'fruta_h', 'company_id': cls.root.id,
            'company_ids': [Command.set((cls.root | cls.branch).ids)]})
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
            'name': code + ' group', 'especie_id': species.id,
            'company_id': cls.root.id,
            'company_ids': [Command.set((cls.root | cls.branch).ids)]})
        return cls.env['step.variedad'].create({
            'name': code, 'cod_variedad': code, 'especie_id': species.id,
            'grupo_variedad_id': group.id, 'company_id': cls.root.id,
            'company_ids': [Command.set((cls.root | cls.branch).ids)]})

    def _as_accountant(self, records):
        return records.with_user(self.operator).with_context(allowed_company_ids=self.branch.ids)

    def _case(self, *, kilos=20, price=5, species=None, variety=None,
              expense=None, date='2026-11-09', input_tags=None, snapshot=False, tag_values=None):
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
        if tag_values:
            tag.write(tag_values)
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

    def _legacy_draft(self, *, price=5, taxes=None):
        """A pre-proforma monthly bill, linked by the existing OT foreign key."""
        production, tag, source = self._case(snapshot=True)
        taxes = self.vat if taxes is None else taxes
        bill = self.env['account.move'].with_company(self.branch).create({
            'move_type': 'in_invoice', 'partner_id': self.producer.id,
            'company_id': self.branch.id, 'currency_id': self.branch.currency_id.id,
            'journal_id': self.journal.id, 'invoice_date': '2026-11-30',
            'ref': 'Legacy monthly draft QA171',
            'l10n_latam_document_type_id': self.env.ref('l10n_cl.dc_a_f_dte').id,
            'l10n_latam_document_number': '17190',
            'invoice_line_ids': [Command.create({
                'name': 'Legacy monthly fruit', 'product_id': self.base.id,
                'product_uom_id': self.base.uom_id.id,
                'account_id': self.expense.id, 'quantity': 20, 'price_unit': price,
                'tax_ids': [Command.set(taxes.ids)]})]})
        production.with_context(_packing_valuation=_VALUATION, _packing_control=_INTERNAL).write({
            'purchase_bill_id': bill.id})
        return production, tag, source, bill

    def _legacy_review(self, wizard):
        action = wizard.action_prepare_bills()
        self.assertEqual(action['res_model'], 'step.packing.fruit.proforma.migration')
        return self._as_accountant(self.env[action['res_model']].browse(action['res_id']))

    def _assert_legacy_migration_rollback(self, *, price=5, taxes=None):
        production, tag, source, bill = self._legacy_draft(price=price, taxes=taxes)
        review = self._legacy_review(self._wizard())
        fields = ['state', 'name', 'ref', 'invoice_date', 'currency_id',
                  'invoice_line_ids', 'line_ids', 'amount_untaxed', 'amount_tax',
                  'amount_total', 'write_date', 'step_fruit_migrated_proforma_id']
        before_bill = bill.read(fields)[0]
        before_lines = bill.invoice_line_ids.read([
            'product_id', 'quantity', 'price_unit', 'tax_ids', 'price_subtotal', 'price_total'])
        before_stock = self._stock_counts()
        before_orders = self.env['purchase.order'].search_count([('company_id', '=', self.branch.id)])
        # Deliberately catch without an outer savepoint: the migration itself
        # must restore cancellation, source links, and any partially created PO.
        with self.assertRaises(ValidationError):
            review.action_move_to_proforma()
        bill.invalidate_recordset()
        production.invalidate_recordset()
        tag.invalidate_recordset()
        self.assertEqual(bill.read(fields)[0], before_bill)
        self.assertEqual(bill.invoice_line_ids.read([
            'product_id', 'quantity', 'price_unit', 'tax_ids', 'price_subtotal', 'price_total']), before_lines)
        self.assertEqual(production.purchase_bill_id, bill)
        self.assertFalse(tag.step_fruit_proforma_id)
        self.assertFalse(bill.step_fruit_migration_proforma_ids)
        self.assertEqual(self.env['purchase.order'].search_count([
            ('company_id', '=', self.branch.id)]), before_orders)
        self.assertEqual(self._stock_counts(), before_stock)

