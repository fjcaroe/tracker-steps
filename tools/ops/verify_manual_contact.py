"""Native supplier creation and local lookup without external enrichment."""
import importlib
import json
from pathlib import Path
from lxml import etree
from unittest.mock import patch
from odoo.tools import config
from native_business_profile import scoped_business_environment

try:
    for name,version in EXPECTED.items():
        module=env['ir.module.module'].search([('name','=',name)])
        assert module.state=='installed' and module.latest_version==version
        assert Path(importlib.import_module('odoo.addons.'+name).__file__).resolve().parent==Path(ROOT)/name
    scoped=scoped_business_environment(env)
    model=scoped['res.partner']
    arch=etree.fromstring(model.get_view(view_type='form')['arch'])
    assert not arch.xpath("//field[@widget='field_partner_autocomplete']")
    visible=scoped['ir.ui.menu']._visible_menu_ids()
    menus=scoped['ir.ui.menu'].search([('id','in',list(visible)),('action','!=',False)])
    assert menus.filtered(lambda m:m.action._name=='ir.actions.act_window' and m.action.res_model=='res.partner')
    previous=config['test_enable'];config['test_enable']=True
    try:
        from odoo.tests import Form
    finally:
        config['test_enable']=previous
    Form(model)
    content,_=scoped['ir.qweb']._get_asset_content('web.assets_backend')
    entries=[entry for entry in content if entry['url'].endswith('step_partner_manual_entry/static/src/js/partner_field.js')]
    assert len(entries)==1 and Path(entries[0]['filename']).resolve()==Path(ROOT)/'step_partner_manual_entry/static/src/js/partner_field.js'
    if env.cr.dbname.startswith('MANAGEMENT_QA_'):
        bundle=scoped['ir.qweb']._get_asset_bundle('web.assets_backend')
        js=''.join(attachment.raw.decode() for attachment in bundle.js())
        assert '@step_partner_manual_entry/js/partner_field' in js
    with patch.object(type(scoped['iap.autocomplete.api']),'_contact_iap',side_effect=AssertionError('External autocomplete must not run')):
        assert model.autocomplete_by_name('QA Supplier')==[]
        assert model.autocomplete_by_vat('CL123')==[]
        assert model.enrich_by_duns('0001')=={}
        if env.cr.dbname.startswith('MANAGEMENT_QA_'):
            form=Form(model.with_context(default_supplier_rank=1,default_company_type='company'))
            form.name='QA Manual Agricultural Supplier'
            partner=form.save()
            assert partner.is_company and partner.supplier_rank>0
            assert partner.id in [item[0] for item in model.name_search('QA Manual Agricultural Supplier')]
            Form(partner)
            print('MANUAL_CONTACT_OPERATOR_FLOW_OK rollback_required=True')
    print('MANAGEMENT_REGISTRY_OK '+json.dumps({'versions':EXPECTED,'existing_profile':scoped.uid,'company_id':scoped.company.id,'native_menu_and_form':True,'paid_autocomplete_disabled':True,'local_lookup_preserved':True,'writes':False}))
finally:
    env.cr.rollback()
