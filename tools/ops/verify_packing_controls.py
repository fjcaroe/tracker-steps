import importlib
import json
from pathlib import Path
from lxml import etree
from odoo.tools import config
from native_business_profile import scoped_business_environment

try:
    for name,version in EXPECTED.items():
        installed=env['ir.module.module'].search([('name','=',name)])
        assert installed.state=='installed' and installed.latest_version==version
        assert Path(importlib.import_module('odoo.addons.'+name).__file__).resolve().parent==Path(ROOT)/name
    scoped=scoped_business_environment(env)
    rules=scoped['step.packing.analytic.rule'].search([('company_id','=',scoped.company.id)])
    assert {rule.origin for rule in rules if rule.apply}=={'season','species','ot'}
    menu=scoped.ref('step_packing_analytics.rules_menu')
    assert menu.id in scoped['ir.ui.menu']._visible_menu_ids()
    for app in ('packing','export','producers'):
        previous=None
        for level in ('read','operation','manager'):
            group=scoped.ref('step_application_profiles.%s_%s'%(app,level))
            if previous:assert previous in group.trans_implied_ids
            assert scoped.ref('account.group_account_manager') not in group.trans_implied_ids
            assert scoped.ref('base.group_system') not in group.trans_implied_ids
            previous=group
    view=scoped.ref('step_packing_operations.view_packing_production_form')
    model=scoped['step.packing.production']
    arch=etree.fromstring(model.get_view(view_id=view.id,view_type='form')['arch'])
    assert arch.xpath("//button[@name='action_apply_packing_analytics']")
    assert arch.xpath("//page[@name='packing_analytics']//field[@name='step_analytic_summary']")
    previous=config['test_enable'];config['test_enable']=True
    try:
        from odoo.tests import Form
    finally:config['test_enable']=previous
    Form(model.search([],limit=1) or model,view=view)
    user_view=scoped['res.users'].get_view(view_id=scoped.ref('base.view_users_form').id,view_type='form')
    assert user_view['arch']
    original=model.search([('name','=','OT/2026/00040')])
    if original:
        assert original.state in ('closed','costed','accounted')
        assert all(picking.state=='done' for picking in original.input_picking_id|original.material_picking_id|original.output_picking_id)
        assert original.step_packing_transfer_id.state=='done'
        assert original.material_picking_id.location_id==scoped.company.step_packing_material_location_id
        assert original.input_picking_id.location_id==scoped.company.step_packing_fruit_location_id
        assert all(product.is_storable for product in original.step_packing_output_tag_ids.step_tag_line_ids.product_id)
        print('T121_CONFIRMED_CYCLE_OK writes=False')
    clone=False
    if env.cr.dbname.startswith('MANAGEMENT_QA_'):
        from probe_packing_controls import verify_flow
        verify_flow(env,scoped);clone=True
    print('MANAGEMENT_REGISTRY_OK '+json.dumps({'tickets':[114,121,122],'versions':EXPECTED,
        'existing_profile':scoped.uid,'company_id':scoped.company.id,'native_menu_and_form':True,
        'profile_groups':9,'analytic_rules':True,'clone_flow':clone,'writes':False}))
finally:env.cr.rollback()
