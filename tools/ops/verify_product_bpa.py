"""T127 actual existing product form, native master and no Studio field runtime."""
import importlib
import json
from pathlib import Path
from lxml import etree
from odoo.tools import config
from native_business_profile import scoped_business_environment

try:
    for name, version in EXPECTED.items():
        module = env['ir.module.module'].search([('name','=',name)])
        assert module.state == 'installed' and module.latest_version == version
        assert Path(importlib.import_module('odoo.addons.'+name).__file__).resolve().parent == Path(ROOT)/name
    scoped = scoped_business_environment(env)
    template = scoped['product.template']
    arch = etree.fromstring(template.get_view(view_type='form')['arch'])
    fields = ('registration_concentration','registration_formulation','registration_formulation_code','registration_aptitude_id','registration_authorization_holder','registration_first_authorized_on','registration_authorization_expires_on','agriculture_active_ingredient_id','agriculture_max_withholding_days','agriculture_eu_withholding_days','agriculture_us_withholding_days','agriculture_max_applications')
    for field in fields:
        assert arch.xpath("//page[@name='bpa']//field[@name='%s']" % field), field
    assert not arch.xpath("//page[@name='bpa_registration']")
    assert not env['ir.model'].search([('model','=','x_aptitud_plaguicidas')])
    model = scoped['step.agriculture.pesticide.aptitude']
    assert not env['ir.model.fields'].search([('model','=',model._name),('state','=','manual')])
    menu = scoped.ref('step_product_bpa.menu_aptitudes')
    assert menu.id in scoped['ir.ui.menu']._visible_menu_ids()
    assert menu.action.res_model == model._name
    previous=config['test_enable'];config['test_enable']=True
    try:
        from odoo.tests import Form
    finally:
        config['test_enable']=previous
    product=template.search([],limit=1)
    assert product
    Form(product)
    Form(model)
    if env.cr.dbname.startswith('MANAGEMENT_QA_'):
        aptitude=model.create({'name':'QA BPA operator', 'code':'001/B'})
        with Form(product) as form:
            form.registration_aptitude_id=aptitude
            form.registration_concentration='48 %p/v (480 g/l)'
            form.registration_first_authorized_on='1985-09-04'
            form.registration_authorization_expires_on='2025-09-04'
        assert product.registration_aptitude_id == aptitude
        assert product.registration_concentration=='48 %p/v (480 g/l)'
        Form(aptitude)
        print('T127_OPERATOR_NATIVE_FORM_FLOW_OK rollback_required=True')
    print('MANAGEMENT_REGISTRY_OK '+json.dumps({'ticket':127,'versions':EXPECTED,'native_menu_form':True,'existing_profile':scoped.uid,'company_id':scoped.company.id,'writes':False}))
finally:
    env.cr.rollback()
