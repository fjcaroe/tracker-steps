"""T145 native branch consolidation and company column."""
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
    menu=scoped.ref('step_export.menu_step_export_consult_tags')
    assert menu.id in scoped['ir.ui.menu']._visible_menu_ids()
    action=scoped['ir.actions.act_window']._for_xml_id('step_export.action_export_consult_tags')
    assert action['context']['step_export_branch_scope'] is True
    assert all(scoped['res.company'].browse(cid) in scoped.user.company_ids for cid in action['context']['allowed_company_ids'])
    view=scoped['stock.quant.package'].get_view(view_id=scoped.ref('step_export.view_export_fruit_tag_list').id,view_type='list')
    assert etree.fromstring(view['arch']).xpath("//field[@name='company_id'][@optional='show']")
    form=scoped['step.export.export'].get_view(view_id=scoped.ref('step_export.view_step_export_shipment_form').id,view_type='form')
    assert etree.fromstring(form['arch']).xpath("//field[@name='dispatch_guide_ids'][contains(@domain,'step_branch_company_ids')]")
    print('MANAGEMENT_REGISTRY_OK '+json.dumps({'ticket':145,'versions':EXPECTED,'existing_profile':scoped.uid,'native_menu_and_form':True,'branch_scope':action['context']['allowed_company_ids'],'writes':False}))
finally:
    env.cr.rollback()
