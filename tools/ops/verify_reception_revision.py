"""Verify T118's effective reception action, native fields and business profile."""
import importlib
import json
from pathlib import Path
from lxml import etree
from odoo.tools import config
from odoo.tools.safe_eval import safe_eval
from native_business_profile import scoped_business_environment

try:
    for name, version in EXPECTED.items():
        module = env['ir.module.module'].search([('name', '=', name)])
        assert module.state == 'installed' and module.latest_version == version
        assert Path(importlib.import_module('odoo.addons.' + name).__file__).resolve().parent == Path(ROOT) / name
    scoped = scoped_business_environment(env)
    menu = scoped.ref('step_packing_operations.menu_packing_reception_process')
    assert menu.id in scoped['ir.ui.menu']._visible_menu_ids()
    action = scoped.ref('step_inventory_packing.action_steps_fruit_process_reception')
    assert menu.action == action
    view = scoped.ref('step_packing_reception_revision.view_process_reception_form')
    assert view in action.view_ids.mapped('view_id')
    assert action.views[:2] == [(scoped.ref('stock.vpicktree').id, 'list'), (view.id, 'form')]
    model = scoped['stock.picking']
    list_arch = etree.fromstring(model.get_view(view_id=scoped.ref('stock.vpicktree').id, view_type='list')['arch'])
    assert {'name','partner_id','state'} <= set(list_arch.xpath('//field/@name'))
    listed = model.search(safe_eval(action.domain), limit=5)
    assert all(row.picking_type_code == 'incoming' and row.step_fruit_reception_kind == 'process' for row in listed)
    arch = etree.fromstring(model.get_view(view_id=view.id, view_type='form')['arch'])
    expected = ['product_id','step_fruit_pallet_type_id','step_fruit_pallet_qty','product_packaging_id',
                'step_fruit_packaging_qty','product_uom','product_uom_qty']
    columns = arch.xpath("//field[@name='move_ids_without_package']/list/field/@name")
    start = columns.index('product_id')
    assert columns[start:start+7] == expected
    assert arch.xpath("//page[@name='step_fruit_freights']//field[@name='fruit_freight_paid']")
    assert not arch.xpath("//page[@name='step_packing_fruit']//field[@name='fruit_freight_paid']")
    for old in ('fruit_class_id','fruit_weighing_type','fruit_grower_contract'):
        assert not arch.xpath("//page[@name='step_packing_fruit']//field[@name='%s']" % old)
    assert model._fields['step_fruit_origin_class_id'].comodel_name == 'step.management.fruit.class'
    assert model._fields['step_fruit_contract_id'].comodel_name == 'step.producer.purchase.contract'
    assert set(dict(model._fields['step_fruit_type']._description_selection(scoped))) == {'conventional','organic'}
    assert arch.xpath("//page[@name='step_packing_fruit']//field[@name='step_fruit_type']")
    assert arch.xpath("//field[@name='fruit_tag_line_ids']/list/field[@name='package_id']/@column_invisible") == ['True']
    assert arch.xpath("//field[@name='step_container_transfer_ids']/@invisible") == ['1']
    assert arch.xpath("//button[@name='action_prepare_fruit_stock']/@invisible") == ['1']
    tag_columns=arch.xpath("//field[@name='fruit_tag_line_ids']/list/field")
    visible=[n.get('name') for n in tag_columns if n.get('column_invisible') not in ('1','True') and n.get('optional')!='hide']
    assert visible[:13]==['sequence','tag_number','product_id','packaging_id','uom_id','caliber_id','category_id','brand','quantity','gross_kg','tare_kg','kilos','step_kg_per_box']
    assert 'net_kg' not in visible
    assert model._fields['step_receiving_packing_id'].comodel_name=='res.partner'
    report_menu=scoped.ref('step_packing_ticket_revision.reports')
    assert report_menu.id in scoped['ir.ui.menu']._visible_menu_ids()
    for category in ('fruit','materials'):
        report=scoped['stock.quant'].action_steps_packing_stock(category)
        assert report['res_model']=='stock.quant' and report['domain']
        scoped['stock.quant'].search(report['domain'],limit=1)
    production=scoped['step.packing.production']
    production_arch=etree.fromstring(production.get_view(view_type='form')['arch'])
    assert production_arch.xpath("//group[@name='ot_identity_left']/field/@name")[:3]==['packing_partner_id','date','step_packing_order_id']
    assert production_arch.xpath("//field[@name='fruit_fundo_id']")[0].getnext().get('name')=='company_id'
    print('T132_T134_NATIVE_REPORTS_AND_HEADERS_OK')
    previous = config['test_enable']; config['test_enable'] = True
    try:
        from odoo.tests import Form
    finally:
        config['test_enable'] = previous
    record = model.search([('step_fruit_reception_kind','=','process')], limit=1)
    Form(record or model.with_context(default_step_fruit_reception_kind='process'), view=view)
    clone_flow = False
    if env.cr.dbname.startswith('MANAGEMENT_QA_'):
        from probe_reception_flow import verify_flow
        verify_flow(env, scoped)
        clone_flow = True
    print('MANAGEMENT_REGISTRY_OK ' + json.dumps({'ticket':120,'versions':EXPECTED,
        'existing_profile':scoped.uid,'company_id':scoped.company.id,'native_menu_and_form':True,
        'automatic_tags':True,'simplified_form':True,'clone_flow':clone_flow,'native_list':True,'list_first':True,'fruit_selector':True,'operations_order':True,'freights_tab':True,'master_class':True,'contract_scope':True,'writes':False}))
finally:
    env.cr.rollback()
