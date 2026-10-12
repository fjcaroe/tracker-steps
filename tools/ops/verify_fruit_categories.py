"""Verify T73 shared masters, effective UI, receipt and contract pricing; rollback samples."""
import importlib,json
from pathlib import Path
from types import SimpleNamespace
from lxml import etree
from odoo.tests.common import new_test_user
from odoo.addons.step_fruit_category_unification.tests.test_categories import FruitCategoriesCase

try:
    for name,version in EXPECTED.items():
        module=env['ir.module.module'].search([('name','=',name)])
        assert module.state=='installed' and module.latest_version==version
        assert Path(importlib.import_module('odoo.addons.'+name).__file__).resolve().parent==Path(ROOT)/name
    company=env['res.company'].search([('vat','=','76943293-0')],limit=1) or env.company
    env=env(context=dict(env.context,allowed_company_ids=company.ids,no_reset_password=True,
                        tracking_disable=True,mail_create_nosubscribe=True))
    for model in env.registry.models:
        for field in env[model]._fields.values():
            assert getattr(field,'comodel_name',None) not in ('step.packing.fruit.category','step.packing.fruit.class')
    user=new_test_user(env,login='qa-t73-reader',groups='stock.group_stock_manager',company_id=company.id,company_ids=[(6,0,company.ids)])
    visible=env['ir.ui.menu'].with_user(user)._visible_menu_ids()
    action=env.ref('step_management_costs.action_fruit_category')
    for xmlid in ('step_packing_operations.menu_packing_config_fruit_category','step_packing.menu_packing_fruta_fruit_category','step_packing.menu_step_packing_fruit_category'):
        menu=env.ref(xmlid);assert menu.id in visible and menu.action==action
    for key in ('packing','export','producer'):
        menu=env.ref('step_fruit_category_unification.'+key+'_class')
        assert menu.id in visible and menu.action==env.ref('step_management_costs.action_fruit_class')
    for key,model in [('category','step.management.fruit.category'),('class','step.management.fruit.class')]:
        arch=etree.fromstring(env[model].with_user(user).get_view(view_id=env.ref('step_fruit_category_unification.'+key+'_form').id,view_type='form')['arch'].encode())
        assert arch.xpath('.//field[@name="code"]') and arch.xpath('.//field[@name="name"]')
        if key=='class':assert arch.xpath('.//field[@name="category_id"]')
    category_list=etree.fromstring(env[action.res_model].with_user(user).get_view(view_id=env.ref('step_management_costs.view_fruit_category_list').id,view_type='list')['arch'].encode())
    assert not category_list.xpath('.//field[@name="step_contract_category_id"]')
    case=SimpleNamespace(env=env)
    picking,category,fruit_class=FruitCategoriesCase.sample(case)
    assert picking.state=='done' and picking.fruit_category_id==category and picking.fruit_class_id==category
    assert picking.fruit_tag_line_ids.mapped('category_id')==category
    contract,line=FruitCategoriesCase.contract_sample(case,picking,category)
    price=line.resolve_variant_price(contract,line.product_id,line.species_id,category=category.step_contract_category_id)
    assert price==line and line.amount==20
    assert fruit_class.category_id==category and category.step_contract_category_id==category
    for model,column in [('stock.picking','fruit_category_id'),('stock.picking','fruit_class_id'),
                         ('step.packing.picking.tag.line','category_id'),('step.producer.purchase.contract.product','category_id')]:
        assert env[model]._fields[column].comodel_name=='step.management.fruit.category'
        for record in env[model].search([(column,'!=',False)]):
            assert record[column].company_id==record.company_id, 'Cross-company category relation'
    form=etree.fromstring(picking.with_user(user).get_view(view_id=env.ref('stock.view_picking_form').id,view_type='form')['arch'].encode())
    assert form.xpath('.//field[@name="fruit_category_id"]') and form.xpath('.//field[@name="fruit_class_id"]')
    other=env['res.company'].create({'name':'QA T73 outsider'})
    outsider=new_test_user(env,login='qa-t73-outsider',groups='stock.group_stock_user',company_id=other.id,company_ids=[(6,0,other.ids)])
    assert not env['step.management.fruit.class'].with_user(outsider).with_context(allowed_company_ids=other.ids).search([('id','=',fruit_class.id)])
    print('MANAGEMENT_REGISTRY_OK '+json.dumps({'tickets':[73],'versions':EXPECTED,'shared_categories':True,
        'class_menus':True,'forms':True,'receipt_validated':True,'contract_price':True,'company_security':True,
        'legacy_relations_retired':True,'category_action':action.id,'class_action':env.ref('step_management_costs.action_fruit_class').id}))
finally:
    env.cr.rollback()
