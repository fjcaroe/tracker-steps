"""T144: existing operator, native company filter and no stock changes."""
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
    menu=scoped.ref('step_packing_operations.menu_packing_production')
    assert menu.id in scoped['ir.ui.menu']._visible_menu_ids()
    form=scoped['stock.quant.package'].get_view(view_id=scoped.ref('stock.view_quant_package_form').id,view_type='form')
    arch=etree.fromstring(form['arch'])
    assert arch.xpath("//field[@name='is_fruit_tag']")
    assert 'company_id' in scoped['stock.quant.package'].fields_get(['company_id'])
    if scoped.user.has_group('base.group_multi_company'):
        assert arch.xpath("//field[@name='company_id']")
    tags=env['stock.quant.package'].search([('is_fruit_tag','=',True),('step_tag_kind','in',['E','N']),('step_packing_production_id','!=',False)])
    assert all(tag.company_id==tag.step_packing_production_id.company_id for tag in tags)
    visible=tags.filtered(lambda tag: tag.company_id in scoped.companies)
    if visible:
        found=scoped['stock.quant.package'].search([('id','in',visible.ids),('company_id','in',scoped.companies.ids)])
        assert found==visible.sorted(key=lambda tag: tag.name) or set(found.ids)==set(visible.ids)
    print('MANAGEMENT_REGISTRY_OK '+json.dumps({'ticket':144,'versions':EXPECTED,'existing_profile':scoped.uid,'native_menu_and_form':True,'company_filter':True,'verified_existing_tags':len(tags),'writes':False}))
finally:
    env.cr.rollback()
