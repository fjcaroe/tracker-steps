"""Monthly bills must use the same accounting configuration as native purchases."""
from odoo import Command
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged
from odoo.tests.common import new_test_user

from ..models.process_control import _INTERNAL


@tagged('post_install', '-at_install', 'step_packing_operations')
class TestMonthlyFruitAccounting(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.root = cls.env.company
        cls.branch = cls.env['res.company'].create({
            'name': 'Monthly fruit accounting branch QA', 'parent_id': cls.root.id})
        cls.env.user.company_ids |= cls.branch
        cls.producer = cls.env['res.partner'].create({
            'name': 'Monthly fruit accounting producer QA', 'is_productor': True})
        cls.species = cls.env['step.especie'].create({
            'name': 'Monthly fruit QA species', 'type_especie': 'frutal', 'group_especie': 'fruta_h'})

        def account(code, name, account_type='expense'):
            return cls.env['account.account'].with_company(cls.root).create({
                'name': name, 'code': code, 'account_type': account_type,
                'reconcile': account_type == 'liability_payable',
                'company_ids': [Command.set(cls.root.ids)]})

        cls.product_expense = account('QA170PROD', 'Monthly fruit product expense QA')
        cls.category_expense = account('QA170CAT', 'Monthly fruit category expense QA')
        cls.override_expense = account('QA170OVR', 'Monthly fruit contract override QA')
        cls.mapped_expense = account('QA170MAP', 'Monthly fruit fiscal mapped expense QA')
        cls.payable = account('QA170PAY', 'Monthly fruit payable QA', 'liability_payable')
        cls.producer.with_company(cls.branch).property_account_payable_id = cls.payable
        cls.category = cls.env['product.category'].with_company(cls.branch).create({
            'name': 'Monthly fruit native account category QA',
            'property_account_expense_categ_id': cls.category_expense.id})
        cls.base = cls.env['product.product'].with_company(cls.branch).create({
            'name': 'Monthly fruit base kilograms QA', 'default_code': 'QA170BASE',
            'step_export_enabled': True, 'categ_id': cls.category.id,
            'uom_id': cls.env.ref('uom.product_uom_kgm').id,
            'uom_po_id': cls.env.ref('uom.product_uom_kgm').id,
            'property_account_expense_id': cls.product_expense.id,
            'supplier_taxes_id': [Command.clear()]})
        cls.finished = cls.env['product.product'].create({
            'name': 'Monthly fruit export carton QA', 'weight': 10,
            'step_export_enabled': True,
            'step_export_base_product_id': cls.base.product_tmpl_id.id})
        cls.journal = cls.env['account.journal'].with_company(cls.branch).create({
            'name': 'Monthly fruit purchase QA', 'code': 'Q170P',
            'type': 'purchase', 'company_id': cls.branch.id})
        cls.branch.step_packing_purchase_journal_id = cls.journal
        cls.operator = new_test_user(cls.env, login='monthly-fruit-accounting-qa',
            groups='account.group_account_manager,stock.group_stock_manager,base.group_multi_company',
            company_id=cls.branch.id, company_ids=[Command.set((cls.root | cls.branch).ids)])

    def _monthly_case(self, override=False):
        # A legacy closed OT is represented without manufacturing or moving stock.
        # The destination-copy probe additionally runs the customer's real orders.
        contract = self.env['step.producer.purchase.contract'].with_company(self.root).create({
            'company_id': self.root.id, 'partner_id': self.producer.id,
            'currency_id': self.branch.currency_id.id})
        source = self.env['step.producer.purchase.contract.product'].create({
            'contract_id': contract.id, 'product_id': self.base.id,
            'species_id': self.species.id, 'quantity': 20,
            'uom_id': self.base.uom_id.id, 'price_unit': 5,
            'debit_account_id': override.id if override else False})
        self.env['step.producer.purchase.contract.installment'].create({
            'contract_id': contract.id, 'product_line_id': source.id,
            'quantity': 20, 'date_due': '2026-11-30'})
        contract.action_confirm()
        tag = self.env['stock.quant.package'].with_company(self.branch).create({
            'name': 'Monthly fruit accounting tag QA', 'company_id': self.branch.id,
            'is_fruit_tag': True, 'step_tag_kind': 'E', 'step_packing_result': 'export',
            'fruit_type': 'conventional', 'step_producer_id': self.producer.id,
            'especie_id': self.species.id,
            'step_tag_line_ids': [Command.create({
                'producer_id': self.producer.id, 'product_id': self.finished.id,
                'quantity': 2, 'boxes': 2, 'kilos': 20})]})
        production = self.env['step.packing.production'].with_company(self.branch).create({
            'company_id': self.branch.id, 'date': '2026-11-09',
            'fruit_grower_id': self.producer.id, 'fruit_species_id': self.species.id,
            'product_id': self.finished.id, 'product_uom_id': self.finished.uom_id.id,
            'step_packing_output_tag_ids': [Command.set(tag.ids)]})
        production.with_context(_packing_control=_INTERNAL).write({'state': 'closed'})
        wizard = self.env['step.packing.monthly.fruit.bill'].with_user(self.operator).with_context(
            allowed_company_ids=self.branch.ids).create({
                'company_id': self.branch.id, 'date_start': '2026-11-01', 'date_end': '2026-11-30',
                'producer_ids': [Command.set(self.producer.ids)], 'contract_id': contract.id})
        return production, wizard, source

    def _assert_native_bill(self, production, wizard, account):
        result = wizard.action_prepare_bills()
        bill = production.purchase_bill_id
        self.assertTrue(bill)
        self.assertEqual(bill.state, 'draft')
        self.assertEqual(bill.company_id, self.branch)
        self.assertEqual(bill.currency_id, self.branch.currency_id)
        self.assertEqual(bill.journal_id, self.branch.step_packing_purchase_journal_id)
        self.assertEqual(bill.invoice_line_ids.product_id, self.base)
        self.assertEqual(bill.invoice_line_ids.account_id, account)
        self.assertEqual(bill.invoice_line_ids.product_uom_id, self.base.uom_id)
        self.assertEqual(bill.invoice_line_ids.quantity, 20)
        self.assertEqual(bill.amount_untaxed, 100)
        self.assertFalse(production.valuation_snapshot)
        self.assertEqual(production.state, 'closed')
        self.assertEqual(bill.line_ids.filtered(lambda line: line.display_type == 'payment_term').account_id,
                         self.payable)
        self.assertAlmostEqual(sum(bill.line_ids.mapped('balance')), 0)
        self.assertEqual(wizard.action_prepare_bills()['domain'], result['domain'])
        self.assertEqual(production.purchase_bill_id, bill)
        return bill

    def test_product_expense_without_contract_account_prepares_same_draft_on_retry(self):
        production, wizard, source = self._monthly_case()
        self.assertFalse(source.debit_account_id)
        self._assert_native_bill(production, wizard, self.product_expense)

    def test_category_expense_is_native_fallback(self):
        self.base.with_company(self.branch).property_account_expense_id = False
        production, wizard, source = self._monthly_case()
        self.assertFalse(source.debit_account_id)
        self._assert_native_bill(production, wizard, self.category_expense)

    def test_contract_expense_overrides_product_account(self):
        production, wizard, source = self._monthly_case(self.override_expense)
        self.assertEqual(source.debit_account_id, self.override_expense)
        self._assert_native_bill(production, wizard, self.override_expense)

    def test_parent_tax_and_fiscal_position_map_native_bill(self):
        def tax(name, percent):
            return self.env['account.tax'].with_company(self.root).create({
                'name': name, 'amount': percent, 'amount_type': 'percent',
                'type_tax_use': 'purchase', 'company_id': self.root.id})

        original_tax = tax('Monthly fruit parent VAT 19 QA', 19)
        mapped_tax = tax('Monthly fruit fiscal VAT 10 QA', 10)
        self.base.supplier_taxes_id = [Command.set(original_tax.ids)]
        fiscal = self.env['account.fiscal.position'].with_company(self.root).create({
            'name': 'Monthly fruit native fiscal position QA', 'company_id': self.root.id,
            'account_ids': [Command.create({'account_src_id': self.override_expense.id,
                                            'account_dest_id': self.mapped_expense.id})],
            'tax_ids': [Command.create({'tax_src_id': original_tax.id, 'tax_dest_id': mapped_tax.id})]})
        self.producer.with_company(self.branch).property_account_position_id = fiscal
        production, wizard, source = self._monthly_case(self.override_expense)
        bill = self._assert_native_bill(production, wizard, self.mapped_expense)
        self.assertEqual(bill.fiscal_position_id, fiscal)
        self.assertEqual(bill.invoice_line_ids.tax_ids, mapped_tax)
        self.assertEqual(bill.amount_tax, 10)
        self.assertEqual(bill.amount_total, 110)

    def test_parent_purchase_journal_retains_branch_invoice_company(self):
        parent_journal = self.env['account.journal'].with_company(self.root).create({
            'name': 'Monthly fruit parent purchases QA', 'code': 'Q170R',
            'type': 'purchase', 'company_id': self.root.id})
        self.branch.step_packing_purchase_journal_id = parent_journal
        production, wizard, source = self._monthly_case()
        bill = self._assert_native_bill(production, wizard, self.product_expense)
        self.assertEqual(bill.journal_id.company_id, self.root)

    def test_missing_product_and_category_accounts_stop_before_bill_creation(self):
        self.base.with_company(self.branch).property_account_expense_id = False
        self.category.with_company(self.branch).property_account_expense_categ_id = False
        production, wizard, source = self._monthly_case()
        with self.assertRaises(UserError) as missing:
            wizard.action_prepare_bills()
        self.assertIn(self.base.display_name, str(missing.exception))
        self.assertFalse(production.purchase_bill_id)
