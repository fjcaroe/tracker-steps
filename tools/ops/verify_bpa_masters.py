"""Read-only T146 verification with existing business profile and native views."""
import importlib
import json
from pathlib import Path
from lxml import etree
from native_business_profile import scoped_business_environment
from odoo.tools.safe_eval import safe_eval

try:
    for name,version in EXPECTED.items():
        module=env['ir.module.module'].search([('name','=',name)])
        assert module.state=='installed' and module.latest_version==version
        assert Path(importlib.import_module('odoo.addons.'+name).__file__).resolve().parent==Path(ROOT)/name
    scoped=scoped_business_environment(env)
    visible=scoped['ir.ui.menu']._visible_menu_ids()
    for alias in ('step_bpa_master_import.menu_bpa_products','step_bpa_master_import.menu_bpa_active_ingredients','step_product_bpa.menu_aptitudes'):
        menu=scoped.ref(alias);assert menu.id in visible
        assert menu.action.res_model in ('product.template','step.agriculture.active.ingredient','step.agriculture.pesticide.aptitude')
    action=scoped.ref('step_bpa_master_import.action_bpa_products')
    assert safe_eval(action.domain)==[('is_bpa','=',True)]
    assert safe_eval(action.context)['default_is_bpa'] is True
    assert scoped.ref('step_product_bpa.menu_aptitudes').parent_id==scoped.ref('step_bpa_master_import.menu_bpa_configuration')
    for model,fields in [('step.agriculture.active.ingredient',('name','cdigo','observacin','active')),
                         ('step.agriculture.pesticide.aptitude',('name','code','notes'))]:
        scoped[model].check_access('create');scoped[model].check_access('write')
        for kind in ('list','form'):
            view=etree.fromstring(scoped[model].get_view(view_type=kind)['arch'])
            assert view.get('import','true') not in ('0','false') and view.get('create','true') not in ('0','false')
            assert all(view.xpath("//field[@name='%s']" % field) for field in fields)
        file=Path(ROOT)/scoped[model].get_import_templates()[0]['template'].lstrip('/')
        assert file.is_file() and file.read_bytes()[:2]==b'PK'
    assert scoped['product.template'].get_view(view_type='form')['arch']
    print('MANAGEMENT_REGISTRY_OK '+json.dumps({'ticket':146,'versions':EXPECTED,'existing_profile':scoped.uid,'native_menu_and_form':True,'native_excel_import':True,'writes':False}))
finally:
    env.cr.rollback()
