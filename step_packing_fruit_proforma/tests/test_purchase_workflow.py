"""T190: exercise the default view and native purchase/receipt/bill lifecycle.

All business records belong to disposable test transactions. No bill is posted.
"""
from lxml import etree
from odoo import Command
from odoo.osv import expression
from odoo.tests import Form, tagged
from odoo.tests.common import new_test_user
from odoo.tools.safe_eval import safe_eval
from .common import FruitProformaCase


@tagged('post_install', '-at_install', 'step_packing_fruit_proforma')
class TestNativePurchaseWorkflow(FruitProformaCase):
    def test_default_form_and_native_actions_remain_purchase(self):
        native = self.env.ref('purchase.purchase_order_form')
        self.assertEqual(self.env['ir.ui.view'].default_view('purchase.order', 'form'), native.id)
        view = self.env['purchase.order'].get_view(view_type='form')
        self.assertEqual(view['id'], native.id)
        arch = etree.fromstring(view['arch'])
        self.assertNotEqual(arch.get('create'), '0')
        self.assertTrue(arch.xpath("//button[@name='button_confirm']"))
        self.assertTrue(arch.xpath("//button[@name='action_create_invoice']"))
        self.assertFalse(arch.xpath("//button[@name='action_fruit_approve']"))
        for xmlid in ('purchase.purchase_rfq', 'purchase.purchase_form_action'):
            action = self.env.ref(xmlid)._get_action_dict()
            form = next(view for view, kind in action['views'] if kind == 'form')
            self.assertEqual(self.env['purchase.order'].get_view(view_id=form, view_type='form')['id'], native.id)
            self.assertFalse(safe_eval(action['context']).get('default_step_fruit_proforma'))

    def test_native_lists_exclude_proformas_and_keep_native_state_filter(self):
        order = self.env['purchase.order'].with_company(self.branch).create(self._ordinary_values())
        production, _, _ = self._case()
        quote = self._prepare(production)
        self._approve(quote)
        for xmlid in ('purchase.purchase_rfq', 'purchase.purchase_form_action', 'purchase.act_res_partner_2_purchase_order'):
            domain = safe_eval(self.env.ref(xmlid).domain)
            self.assertFalse(self.env['purchase.order'].search(expression.AND([domain, [('id', '=', quote.id)]])))
        self.assertIn(order, self.env['purchase.order'].search(safe_eval(self.env.ref('purchase.purchase_rfq').domain)))
        self.assertNotIn(order, self.env['purchase.order'].search(safe_eval(self.env.ref('purchase.purchase_form_action').domain)))
        self.assertEqual(self.env.ref('step_packing_fruit_proforma.menu_purchase_fruit_list').action,
                         self.env.ref('step_packing_fruit_proforma.fruit_proforma_action'))
        self.assertEqual(self.env.ref('step_packing_fruit_proforma.menu_purchase_prepare_fruit').action,
                         self.env.ref('step_packing_operations.action_monthly_fruit_bill'))

    def test_native_form_confirm_receipt_and_vendor_bill(self):
        buyer = new_test_user(self.env, login='qa190-purchase-user',
            groups='purchase.group_purchase_manager,stock.group_stock_manager,account.group_account_manager,base.group_multi_company',
            company_id=self.branch.id, company_ids=[Command.set((self.branch | self.root).ids)])
        product = self.env['product.product'].with_company(self.branch).create({
            'name': 'QA190 ordinary purchased goods', 'type': 'consu', 'is_storable': True,
            'purchase_ok': True, 'purchase_method': 'receive', 'categ_id': self.category.id,
            'property_account_expense_id': self.expense.id, 'supplier_taxes_id': [Command.clear()]})
        model = self.env['purchase.order'].with_user(buyer).with_company(self.branch).with_context(
            allowed_company_ids=(self.branch | self.root).ids, tracking_disable=True,
            mail_notrack=True, mail_create_nosubscribe=True, mail_notify_force_send=False)
        # No explicit view: this is the path that regressed when advance views
        # sorted alphabetically before the native form at the same priority.
        with Form(model) as form:
            form.partner_id = self.producer
            form.picking_type_id = self.warehouse.in_type_id
            with form.order_line.new() as line:
                line.product_id = product
                line.product_qty = 3
                line.price_unit = 10
        order = form.record
        self.assertFalse(order.step_fruit_proforma)
        self.assertEqual(order.state, 'draft')
        order.button_confirm()
        self.assertEqual(order.state, 'purchase')
        self.assertEqual(len(order.picking_ids), 1)
        picking = order.picking_ids
        picking.action_assign()
        picking.move_ids.write({'quantity': 3, 'picked': True})
        picking.with_context(skip_backorder=True).button_validate()
        self.assertEqual(picking.state, 'done')
        self.assertEqual(order.order_line.qty_received, 3)
        order.action_create_invoice()
        self.assertEqual(len(order.invoice_ids), 1)
        bill = order.invoice_ids
        self.assertEqual(bill.state, 'draft')
        self.assertFalse(bill.step_fruit_proforma_id)
        self.assertEqual(bill.invoice_line_ids.purchase_line_id, order.order_line)
        self.assertEqual(bill.amount_untaxed, 30)
        self.assertEqual(order.order_line.qty_invoiced, 3)
