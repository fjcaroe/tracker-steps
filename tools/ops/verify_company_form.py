"""T130 complete native company UI plus independently routed compact forms."""
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
    model=scoped['res.company']
    arch,view=model._get_view(view_type='form')
    assert view==scoped.ref('base.view_company_form')
    full=model.get_view(view_id=view.id,view_type='form')['arch']
    assert model.get_view(view_type='form')['arch']==full
    for name in ('name','vat','currency_id','country_id','phone','email'):
        assert arch.xpath("//field[@name='%s']"%name),name
    # Check the processed user view, including implicit domain dependencies.
    for kind in ('form','list'):
        processed=etree.fromstring(model.get_view(view_type=kind)['arch'])
        contacts=processed.xpath("//field[@name='partner_id']")
        assert contacts and all(n.get('required') in ('False','0') for n in contacts)
    assert model._fields['partner_id'].required
    assert arch.xpath('//notebook/page')
    for name in ('l10n_cl_dte_email','l10n_cl_dte_resolution_number','l10n_cl_dte_resolution_date'):
        assert all(node.get('required') in ('False','0') for node in arch.xpath("//field[@name='%s']"%name))
    assert arch.xpath("//div[@role='alert'][@invisible='not step_sii_configuration_pending']")
    assert len(arch.xpath("//page[@name='steps_previred']"))==1
    assert not arch.xpath(".//field[starts-with(@name,'x_studio_caja_compensacin')]")
    native_pages=[node.get('name') or node.get('string') for node in arch.xpath('//notebook/page')]
    action=scoped.ref('base.action_res_company_form')
    assert action.views[0]==(scoped.ref('base.view_company_tree').id,'list')
    assert model._get_view(view_type='list')[1]==scoped.ref('base.view_company_tree')
    visible=scoped['ir.ui.menu']._visible_menu_ids()
    menus=scoped['ir.ui.menu'].search([('id','in',list(visible)),('action','=','ir.actions.act_window,%s'%action.id)])
    assert menus,'Existing settings company menu required'
    previous=config['test_enable'];config['test_enable']=True
    try:
        from odoo.tests import Form
    finally:
        config['test_enable']=previous
    Form(scoped.company)
    for xmlid,field in [('step_export_shipping_design.folio_company_action','export_folio_mode'),('step_packing_stock_flow.packing_company_action','step_packing_warehouse_id')]:
        special=scoped.ref(xmlid)
        form=next(view for view,kind in special.views if kind=='form')
        assert form and form!=view.id
        special_arch=etree.fromstring(model.get_view(view_id=form,view_type='form')['arch'])
        assert special_arch.xpath("//field[@name='%s']"%field)
        Form(scoped.company,view=form)
    if env.cr.dbname.startswith('MANAGEMENT_QA_'):
        company=scoped.company
        before=company.read(['name','vat','partner_id','currency_id'])[0]
        count=model.search_count([])
        original_phone=company.phone
        form=Form(company)
        form.phone='QA PHONE'
        assert form.phone=='QA PHONE' and company.phone==original_phone
        assert company.read(['name','vat','partner_id','currency_id'])[0]==before
        assert model.search_count([])==count
        pending_before=company.read(['l10n_cl_dte_email','l10n_cl_dte_resolution_number','l10n_cl_dte_resolution_date'])[0]
        with Form(company) as saved:saved.phone='QA PHONE'
        assert company.phone=='QA PHONE'
        assert company.read(['l10n_cl_dte_email','l10n_cl_dte_resolution_number','l10n_cl_dte_resolution_date'])[0]==pending_before
        previous=config['test_enable'];config['test_enable']=True
        try:
            parent=Form(company)
            with parent.child_ids.new() as branch:branch.name='QA Branch Reproduction'
            parent.save()
            child=model.search([('parent_id','=',company.id),('name','=','QA Branch Reproduction')])
            assert len(child)==1 and child.partner_id and child.partner_id!=company.partner_id
            assert child.currency_id==company.currency_id
            assert company.read(['name','vat','partner_id','currency_id'])[0]==before
            assert model.search_count([])==count+1
            print('T131_NATIVE_BRANCH_FLOW_OK generated_contact=True rollback_required=True')
        finally:
            config['test_enable']=previous
        print('T130_NATIVE_COMPANY_FORM_FLOW_OK rollback_required=True')
    print('MANAGEMENT_REGISTRY_OK '+json.dumps({'ticket':130,'versions':EXPECTED,'existing_profile':scoped.uid,'company_id':scoped.company.id,'native_menu_and_form':True,'complete_pages':native_pages,'compact_actions_preserved':True,'writes':False}))
finally:
    env.cr.rollback()
