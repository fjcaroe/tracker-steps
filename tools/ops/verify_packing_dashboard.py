"""T201: native panel, permissions, real company data and drill-down consistency."""
import importlib
import json
from pathlib import Path
from lxml import etree
from native_business_profile import scoped_business_environment

try:
    for name, version in EXPECTED.items():
        module = env['ir.module.module'].search([('name','=',name)])
        assert module.state == 'installed' and module.latest_version == version
        assert Path(importlib.import_module('odoo.addons.'+name).__file__).resolve().parent == Path(ROOT)/name
    scoped = scoped_business_environment(env)
    menu = scoped.ref('step_packing_operations.menu_packing_dashboard')
    assert menu.id in scoped['ir.ui.menu']._visible_menu_ids()
    assert menu.action.tag == 'step_packing_operations.dashboard'
    for model in ('step.packing.production','stock.quant.package'):
        form = scoped[model].get_view(view_type='form')
        assert etree.fromstring(form['arch']).tag == 'form'
    result = scoped['step.packing.order'].get_dashboard_data('month')
    assert result['company_name'] == scoped.company.display_name
    assert len(result['actions']) == 7
    for key, action in result['actions'].items():
        records = scoped[action['res_model']].search(action['domain'])
        assert all(row.company_id == scoped.company for row in records)
        expected = len(records) if key == 'open_productions' else sum(records.mapped('step_actual_kg'))
        assert abs(result['kpis'][key] - expected) < 0.000001
    assets = env['ir.asset']._get_asset_paths('web.assets_backend', {})
    assert any('step_packing_dashboard/static/src/dashboard.js' in str(asset) for asset in assets)
    print('MANAGEMENT_REGISTRY_OK '+json.dumps({'ticket':201,'versions':EXPECTED,'native_menu_and_forms':True,
        'existing_profile':scoped.uid,'company':scoped.company.id,'seven_drilldowns':True,
        'filters':result['filters'],'kpis':result['kpis'],'writes':False},default=str))
finally:
    env.cr.rollback()
