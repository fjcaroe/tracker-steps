"""Verify T175 versions, real effective UI and copy-only native advance flow."""
import json
import hashlib
from pathlib import Path

from lxml import etree
from odoo import Command
from odoo.modules.module import get_module_path
from odoo.tools.safe_eval import safe_eval
from native_business_profile import scoped_business_environment
from producer_advance_checks import verify_ui, verify_advances, verify_reported_dates

def verify_activity_tariffs(scoped, is_copy):
    lists = scoped['product.pricelist']
    producer_action = scoped.ref('step_producer_advances.action_advance_pricelists')._get_action_dict()
    producer_form = dict((kind, view) for view, kind in producer_action['views'])['form']
    assert producer_form == scoped.ref('step_producer_advances.advance_pricelist_form').id
    producer_arch = etree.fromstring(lists.get_view(view_id=producer_form, view_type='form')['arch'])
    assert producer_arch.xpath("//field[@name='step_advance_company_ids']")
    assert producer_arch.xpath("//field[@name='step_advance_market_id']")
    assert not producer_arch.xpath("//field[@name='group_type']")
    template = scoped['product.template']
    if is_copy:
        template = template.sudo().create({
            'name': 'QA tarifa T186', 'type': 'service', 'is_labor': True,
            'grupo_labor': 'manten', 'company_id': scoped.company.id,
        })
    result = {}
    for kind, menu_id in (('propio', 'menu_hr_pricelist_custom'), ('contratista', 'menu_hr_pricelist_contra')):
        menu = scoped.ref('step_hr.' + menu_id)
        assert menu.id in scoped['ir.ui.menu']._visible_menu_ids()
        action = menu.action._get_action_dict()
        form = dict((view_type, view) for view, view_type in action['views'])['form']
        assert form == scoped.ref('step_producer_advances.activity_pricelist_form').id
        arch = etree.fromstring(lists.get_view(view_id=form, view_type='form')['arch'])
        header = {node.get('name') for node in arch.xpath("//sheet//group/field[not(ancestor::field)]")}
        assert {'group_type', 'country_group_ids', 'partner_ids', 'escalonado', 'cost_ids', 'moviliza'} <= header, header
        detail = arch.xpath("//field[@name='item_ids']/form//field")
        names = {node.get('name') for node in detail}
        assert {'labor_id', 'uom_id', 'product_tmpl_id'} <= names, names
        assert not {'tarifa_trato', 'uom_trato'} & names, names
        result[kind] = {'menu': True, 'form': True, 'saved': False}
        if is_copy:
            model = lists.with_context(**safe_eval(action['context']))
            assert model.default_get(['group_type'])['group_type'] == kind
            values = {'name': 'QA tarifa T186 ' + kind, 'company_id': scoped.company.id,
                'item_ids': [Command.create({
                    'applied_on': '1_product', 'compute_price': 'fixed', 'fixed_price': 25000,
                    'labor_id': template.id, 'product_tmpl_id': template.id,
                    'uom_id': scoped.ref('uom.product_uom_kgm').id,
                })]}
            [saved] = model.web_save(values, {'name': {}})
            tariff = model.browse(saved['id'])
            assert tariff.group_type == kind and not tariff.step_advance_price
            assert tariff.item_ids.labor_id == template and tariff.item_ids.product_tmpl_id == template
            assert tariff.item_ids.fixed_price == 25000
            result[kind]['saved'] = True
    return result


try:
    for name, version in EXPECTED.items():
        module=env['ir.module.module'].search([('name','=',name),('state','=','installed')])
        assert module.latest_version==version
        assert Path(get_module_path(name)).resolve()==Path(ROOT)/name
    business=scoped_business_environment(env)
    ui=verify_ui(business)
    flow=verify_advances(env,OUTPUT) if env.cr.dbname.startswith('MANAGEMENT_QA_') else None
    plan_path=Path(OUTPUT)/'t175-date-case.json'
    reported=None
    if plan_path.is_file():
        assert env.cr.dbname=='CERRO_EL_PLOMO' or env.cr.dbname.startswith('MANAGEMENT_QA_CERRO_')
        plan_bytes=plan_path.read_bytes()
        reported=verify_reported_dates(env,json.loads(plan_bytes),run_flow=flow is not None)
        reported['plan_sha256']=hashlib.sha256(plan_bytes).hexdigest()
    print('MANAGEMENT_REGISTRY_OK '+json.dumps({'ticket':175,'versions':EXPECTED,
        'existing_profile':business.uid,'ui':ui,'copy_flow':flow,'reported_dates':reported,'live_business_writes':False}))
    version = tuple(map(int, EXPECTED['step_producer_advances'].split('.')))
    if version >= (18, 0, 1, 1, 0):
        copy = env.cr.dbname.startswith('MANAGEMENT_QA_')
        tariffs = verify_activity_tariffs(business, copy)
        if env.cr.dbname == 'LAB_TAREAS' or env.cr.dbname.startswith('MANAGEMENT_QA_DEVELOPMENT_'):
            eco = env['res.company'].search([('name', '=', 'EcoPlantas')])
            assert len(eco) == 1
            eco_tariffs = verify_activity_tariffs(scoped_business_environment(env, eco), copy)
        else:
            eco_tariffs = None
        print('MANAGEMENT_REGISTRY_OK ' + json.dumps({
            'ticket': 186, 'activities': tariffs, 'ecoplantas': eco_tariffs, 'producer_form': True,
        }))
finally:
    env.cr.rollback()
