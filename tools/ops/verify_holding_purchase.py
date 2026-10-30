"""T142 existing purchase profile, branch selector and native purchase form."""
import importlib
import json
from pathlib import Path
from lxml import etree
from native_business_profile import scoped_business_environment

try:
    for name, version in EXPECTED.items():
        module=env['ir.module.module'].search([('name','=',name)])
        assert module.state=='installed' and module.latest_version==version
        assert Path(importlib.import_module('odoo.addons.'+name).__file__).resolve().parent==Path(ROOT)/name
    scoped=scoped_business_environment(env)
    menus=scoped['ir.ui.menu'].search([('id','in',list(scoped['ir.ui.menu']._visible_menu_ids())),('action','!=',False)])
    assert menus.filtered(lambda m:m.action._name=='ir.actions.act_window' and m.action.res_model=='purchase.order')
    form=scoped['purchase.order'].get_view(view_id=scoped.ref('purchase.purchase_order_form').id,view_type='form')
    arch=etree.fromstring(form['arch'])
    assert arch.xpath("//field[@name='picking_type_id'][contains(@domain,'step_delivery_company_ids')]")
    assert arch.xpath("//field[@name='step_branch_delivery_address_id']")
    print('MANAGEMENT_REGISTRY_OK '+json.dumps({'ticket':142,'versions':EXPECTED,'existing_profile':scoped.uid,'native_menu_and_form':True,'branch_delivery_selector':True,'writes':False}))
finally:
    env.cr.rollback()
