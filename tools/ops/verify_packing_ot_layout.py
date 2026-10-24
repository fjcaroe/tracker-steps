"""Effective OT presentation with an existing destination business profile."""
import importlib
import json
from pathlib import Path
from lxml import etree
from odoo.tools import config
from native_business_profile import scoped_business_environment

try:
    for name,version in EXPECTED.items():
        module=env['ir.module.module'].search([('name','=',name)])
        assert module.state=='installed' and module.latest_version==version
        assert Path(importlib.import_module('odoo.addons.'+name).__file__).resolve().parent==Path(ROOT)/name
    scoped=scoped_business_environment(env)
    menu=scoped.ref('step_packing_operations.menu_packing_production')
    assert menu.id in scoped['ir.ui.menu']._visible_menu_ids()
    assert menu.action.res_model=='step.packing.production'
    model=scoped['step.packing.production']
    arch=etree.fromstring(model.get_view(view_id=scoped.ref('step_packing_operations.view_packing_production_form').id,view_type='form')['arch'])
    assert arch.xpath("//notebook[@name='fruit_details']/page[1]/@name")==['inputs']
    for name,fields in [('ot_identity_left',['company_id','step_packing_order_id','step_packing_line_id','bom_id']),
        ('ot_identity_right',['fruit_grower_id','fruit_fundo_id']),
        ('ot_fruit_contract_left',['fruit_species_id','fruit_variety_id']),
        ('ot_fruit_contract_right',['contract_id','contract_currency_id','contract_amount','purchase_bill_id']),
        ('ot_raw_material_left',['raw_product_id']),('ot_instructions_left',['instruction_id']),
        ('ot_instructions_right',['sales_program_id','sale_order_id'])]:
        fields=[field for field in fields if not (field=='company_id' and not scoped.user.has_group('base.group_multi_company'))
                and not (field=='purchase_bill_id' and not scoped.user.has_group('account.group_account_user'))]
        assert arch.xpath("//group[@name='%s']/field/@name"%name)==fields
    previous=config['test_enable'];config['test_enable']=True
    try:
        from odoo.tests import Form
    finally:
        config['test_enable']=previous
    record=model.search([],limit=1)
    Form(record or model,view='step_packing_operations.view_packing_production_form')
    print('MANAGEMENT_REGISTRY_OK '+json.dumps({'ticket':116,'versions':EXPECTED,
        'existing_profile':scoped.uid,'company_id':scoped.company.id,
        'native_menu_and_form':True,'requested_header':True,'raw_material_first':True,'writes':False}))
finally:
    env.cr.rollback()
