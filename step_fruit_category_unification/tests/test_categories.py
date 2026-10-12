from types import SimpleNamespace
from uuid import uuid4
from lxml import etree
from odoo.tests.common import TransactionCase, new_test_user
from odoo.exceptions import AccessError, UserError
from odoo.addons.step_producer_fruit_reports.tests.test_reports import FruitReportsCase
from ..migration import category_mapping


class FruitCategoriesCase(TransactionCase):
    def sample(self):
        env=self.env(context=dict(self.env.context,no_reset_password=True,tracking_disable=True,mail_create_nosubscribe=True))
        category=env['step.management.fruit.category'].create({'name':'QA T73 export','code':'QA73-'+uuid4().hex[:8]})
        fruit_class=env['step.management.fruit.class'].create({'name':'QA T73 class','code':'QA73-'+uuid4().hex[:8],
            'category_id':category.id,'use_harvest':True,'use_packing':True})
        picking=FruitReportsCase.sample(SimpleNamespace(env=env),done=False)
        picking.write({'fruit_category_id':category.id,'fruit_class_id':category.id})
        picking.fruit_tag_line_ids.category_id=category
        picking.action_prepare_fruit_stock();picking.button_validate()
        assert picking.state=='done'
        return picking,category,fruit_class

    def contract_sample(self,picking,category):
        product=picking.fruit_tag_line_ids[0].product_id
        product.step_export_enabled=True
        contract=self.env['step.producer.purchase.contract'].create({'partner_id':picking.partner_id.id})
        line=self.env['step.producer.purchase.contract.product'].create({'contract_id':contract.id,
            'product_id':product.id,'species_id':picking.fruit_species_id.id,'category_id':category.id,
            'quantity':10,'uom_id':product.uom_id.id,'price_unit':2})
        return contract,line

    def test_receipt_and_contract_use_same_category(self):
        picking,category,fruit_class=self.sample()
        self.assertEqual(picking.fruit_category_id,category)
        self.assertEqual(picking.fruit_class_id,category)
        self.assertEqual(picking.fruit_tag_line_ids.mapped('category_id'),category)
        self.assertEqual(category.step_contract_category_id,category)
        contract,line=self.contract_sample(picking,category)
        selected=line.resolve_variant_price(contract,line.product_id,line.species_id,category=category.step_contract_category_id)
        self.assertEqual(selected,line);self.assertEqual(line.amount,20)
        other=category.copy({'code':'QA73-'+uuid4().hex[:8]})
        with self.assertRaises(UserError):line.resolve_variant_price(contract,line.product_id,line.species_id,category=other)
        self.assertEqual(fruit_class.category_id,category)

    def test_shared_menus_and_effective_forms(self):
        user=new_test_user(self.env(context=dict(self.env.context,no_reset_password=True)),login='qa-t73-stock',groups='stock.group_stock_manager')
        visible=self.env['ir.ui.menu'].with_user(user)._visible_menu_ids()
        for key in ('packing','export','producer'):
            menu=self.env.ref('step_fruit_category_unification.'+key+'_class')
            self.assertIn(menu.id,visible)
            self.assertEqual(menu.action,self.env.ref('step_management_costs.action_fruit_class'))
        menu=self.env.ref('step_packing_operations.menu_packing_config_fruit_category')
        self.assertIn(menu.id,visible)
        self.assertEqual(menu.action,self.env.ref('step_management_costs.action_fruit_category'))
        for key,model in [('category','step.management.fruit.category'),('class','step.management.fruit.class')]:
            arch=etree.fromstring(self.env[model].with_user(user).get_view(view_id=self.env.ref('step_fruit_category_unification.'+key+'_form').id,view_type='form')['arch'].encode())
            self.assertTrue(arch.xpath('.//field[@name="code"]'))
        self.assertEqual(self.env.ref('step_packing.action_step_packing_fruit_class').res_model,'step.management.fruit.category')

    def test_stock_consultation_keeps_management_edit_permissions(self):
        picking,category,fruit_class=self.sample()
        user=new_test_user(self.env(context=dict(self.env.context,no_reset_password=True)),login='qa-t73-read',groups='stock.group_stock_user')
        self.assertTrue(fruit_class.with_user(user).read(['name']))
        with self.assertRaises(AccessError):fruit_class.with_user(user).write({'name':'Cannot edit'})
        manager=new_test_user(self.env(context=dict(self.env.context,no_reset_password=True)),login='qa-t73-management',groups='step_management_costs.group_management_manager')
        fruit_class.with_user(manager).write({'name':'QA T73 configured class'})
        self.assertEqual(fruit_class.name,'QA T73 configured class')

    def test_company_isolation_and_relation_check(self):
        picking,category,fruit_class=self.sample()
        other=self.env['res.company'].create({'name':'QA T73 other'})
        other_category=self.env['step.management.fruit.category'].create({'name':'QA foreign','code':'QA73','company_id':other.id})
        reader=new_test_user(self.env(context=dict(self.env.context,no_reset_password=True)),login='qa-t73-other',groups='stock.group_stock_user',company_id=other.id,company_ids=[(6,0,other.ids)])
        self.assertFalse(self.env['step.management.fruit.class'].with_user(reader).with_context(allowed_company_ids=other.ids).search([('id','=',fruit_class.id)]))
        with self.assertRaises(UserError),self.env.cr.savepoint():
            picking.fruit_category_id=other_category

    def test_explicit_mapping_refuses_missing_and_ambiguous_equivalence(self):
        self.env.cr.execute('INSERT INTO step_packing_fruit_category (name,company_id,sequence) VALUES (%s,%s,10) RETURNING id',('QA73 legacy',self.env.company.id))
        legacy=self.env.cr.fetchone()[0]
        with self.assertRaises(ValueError):category_mapping(self.env.cr,{legacy})
        category=self.env['step.management.fruit.category'].create({'name':'QA target','code':'QA73-'+uuid4().hex[:8]})
        self.env.flush_all()
        self.env.cr.execute('UPDATE step_management_fruit_category SET step_contract_category_id=%s WHERE id=%s',(legacy,category.id))
        self.assertEqual(category_mapping(self.env.cr,{legacy}),{legacy:category.id})
        duplicate=category.copy({'code':'QA73-'+uuid4().hex[:8]})
        self.env.flush_all()
        self.env.cr.execute('UPDATE step_management_fruit_category SET step_contract_category_id=%s WHERE id=%s',(legacy,duplicate.id))
        with self.assertRaises(ValueError):category_mapping(self.env.cr,{legacy})

    def test_no_active_business_relation_to_legacy_master(self):
        for model in self.env.registry.models:
            for field in self.env[model]._fields.values():
                self.assertNotIn(getattr(field,'comodel_name',None),('step.packing.fruit.category','step.packing.fruit.class'))
