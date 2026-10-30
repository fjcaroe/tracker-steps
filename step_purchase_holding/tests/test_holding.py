from odoo import Command
from odoo.tests import TransactionCase, tagged, Form, new_test_user
from odoo.exceptions import ValidationError, UserError


@tagged('post_install', '-at_install')
class HoldingCase(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.parent = cls.env['res.company'].create({'name': 'Private T142 holding'})
        cls.branch = cls.env['res.company'].create({'name': 'Private T142 branch', 'parent_id': cls.parent.id})
        cls.foreign = cls.env['res.company'].create({'name': 'Private T142 unrelated'})
        cls.wh = cls.env['stock.warehouse'].search([('company_id','=',cls.branch.id)],limit=1)
        if not cls.wh:
            cls.wh = cls.env['stock.warehouse'].create({'name':'Private T142 warehouse','code':'B142','company_id':cls.branch.id})
        cls.user = new_test_user(cls.env(context=dict(cls.env.context,no_reset_password=True)), login='private-t142-buyer',
            groups='purchase.group_purchase_manager,stock.group_stock_manager', company_id=cls.parent.id,
            company_ids=[Command.set((cls.parent|cls.branch|cls.foreign).ids)])
        cls.scope = cls.env(user=cls.user, su=False, context=dict(cls.env.context,allowed_company_ids=(cls.parent|cls.branch|cls.foreign).ids))
        cls.supplier = cls.env['res.partner'].create({'name':'Private T142 supplier'})
        cls.product = cls.env['product.product'].create({'name':'Private T142 product','is_storable':True})

    def test_native_form_selects_branch_before_lines(self):
        with Form(self.scope['purchase.order']) as form:
            form.partner_id = self.supplier
            form.picking_type_id = self.wh.in_type_id
            self.assertEqual(form.company_id, self.branch)
        order = form.record
        self.assertEqual(order.step_branch_delivery_address_id, self.branch.partner_id)
        self.assertIn(self.branch,order.step_delivery_company_ids)
        self.assertNotIn(self.foreign,order.step_delivery_company_ids)

    def test_confirmed_order_and_receipt_belong_to_branch(self):
        order = self.scope['purchase.order'].create({'partner_id':self.supplier.id,'company_id':self.parent.id,
            'picking_type_id':self.wh.in_type_id.id,'order_line':[Command.create({'product_id':self.product.id,
                'name':'Private T142 line','product_qty':2,'product_uom':self.product.uom_po_id.id,
                'price_unit':10,'date_planned':'2026-11-02 12:00:00'})]})
        order.button_confirm()
        self.assertEqual(order.company_id,self.branch)
        self.assertTrue(order.picking_ids)
        self.assertEqual(order.picking_ids.company_id,self.branch)
        self.assertEqual(order.picking_ids.location_dest_id,self.wh.lot_stock_id)
        self.assertEqual(order.order_line.company_id,self.branch)
        receipt=order.picking_ids.with_context(allowed_company_ids=self.branch.ids)
        receipt.move_ids.quantity=2
        receipt.button_validate()
        self.assertEqual(receipt.state,'done')
        quants=self.scope['stock.quant'].search([('product_id','=',self.product.id),('location_id','=',self.wh.lot_stock_id.id)])
        self.assertEqual(sum(quants.mapped('quantity')),2)
        self.assertEqual(quants.company_id,self.branch)

    def test_unrelated_company_rejected(self):
        with self.cr.savepoint(),self.assertRaises(ValidationError):
            self.scope['purchase.order'].create({'partner_id':self.supplier.id,'company_id':self.foreign.id,'picking_type_id':self.wh.in_type_id.id})

    def test_unselected_branch_rejected(self):
        scope=self.scope(context=dict(self.scope.context,allowed_company_ids=self.parent.ids))
        with self.cr.savepoint(),self.assertRaises((ValidationError,UserError)):
            scope['purchase.order'].create({'partner_id':self.supplier.id,'picking_type_id':self.wh.in_type_id.id})
