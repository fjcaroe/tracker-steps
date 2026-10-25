"""T121 effective source, company configuration, native form and private flow."""
import importlib
import json
from pathlib import Path
from lxml import etree
from odoo.tools import config
from native_business_profile import scoped_business_environment

try:
    for name, version in EXPECTED.items():
        module = env['ir.module.module'].search([('name', '=', name)])
        assert module.state == 'installed' and module.latest_version == version
        assert Path(importlib.import_module('odoo.addons.' + name).__file__).resolve().parent == Path(ROOT) / name
    scoped = scoped_business_environment(env)
    company = scoped.company
    warehouse = company.step_packing_warehouse_id
    assert warehouse and warehouse.company_id == company
    company._check_packing_locations()
    assert company.step_packing_fruit_location_id and company.step_packing_material_location_id
    model = scoped['step.packing.production']
    action = scoped.ref('step_packing_operations.action_packing_production')
    menus = scoped['ir.ui.menu'].search([('action', '=', 'ir.actions.act_window,%s' % action.id)])
    assert set(menus.ids) & set(scoped['ir.ui.menu']._visible_menu_ids())
    view = scoped.ref('step_packing_operations.view_packing_production_form')
    arch = etree.fromstring(model.get_view(view_id=view.id, view_type='form')['arch'])
    for name in ('step_stock_warehouse_id','step_stock_fruit_location_id','step_stock_material_location_id',
                 'step_packing_transfer_id','input_picking_id','material_picking_id','output_picking_id'):
        assert arch.xpath("//page[@name='packing_stock_flow']//field[@name='%s']" % name)
    previous = config['test_enable']; config['test_enable'] = True
    try:
        from odoo.tests import Form
    finally:
        config['test_enable'] = previous
    Form(model.search([], limit=1) or model, view=view)
    config_action = scoped.ref('step_packing_stock_flow.packing_company_action')
    config_menu = scoped.ref('step_packing_stock_flow.packing_company_menu')
    assert config_menu.id in scoped['ir.ui.menu']._visible_menu_ids()
    assert config_menu.action == config_action
    Form(company, view='step_packing_stock_flow.packing_company_form')
    flow = False
    if env.cr.dbname.startswith('MANAGEMENT_QA_'):
        from probe_packing_stock_flow import verify_flow
        verify_flow(env, scoped)
        flow = True
    print('MANAGEMENT_REGISTRY_OK ' + json.dumps({'ticket':121, 'versions':EXPECTED,
        'existing_profile':scoped.uid, 'company_id':company.id, 'native_menu_and_form':True,
        'packing_warehouse':warehouse.id, 'material_location':company.step_packing_material_location_id.id,
        'fruit_location':company.step_packing_fruit_location_id.id, 'configured_sources':True,
        'traceable_transfer':True, 'clone_flow':flow, 'writes':False}))
finally:
    env.cr.rollback()
