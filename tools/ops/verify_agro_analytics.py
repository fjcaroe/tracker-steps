"""Effective native report/forms/menus/comparison and asset probe; always rolled back."""
import importlib, json
from pathlib import Path
try:
    for name, version in EXPECTED.items():
        module=env['ir.module.module'].search([('name','=',name)])
        assert module.state=='installed' and module.latest_version==version
        assert Path(importlib.import_module('odoo.addons.'+name).__file__).resolve().parent==Path(ROOT)/name
    action=env.ref('step_export.action_export_shipment_overview')
    assert action.res_model=='step.export.shipment.report' and action.view_mode=='pivot,graph,list,form'
    report=env[action.res_model]
    for kind in ('pivot','graph','list','form','search'):
        result=report.get_view(view_id=env.ref('step_agro_analytics.shipment_'+kind).id,view_type=kind)
        assert result['arch']
    line=env['step.packing.line'].get_view(view_id=env.ref('step_packing.view_step_packing_line_form').id,view_type='form')
    assert 'standard_ids' in line['arch'] and 'kg_hour' in line['arch']
    for name in ('dispatch_order','stock_reservation'):
        assert not env.ref('step_export.menu_step_export_'+name).active
    for kind in ('packing','producers'):
        result=env['step.packing.order'].operational_comparison(kind,{})
        assert len(result['tables'])==2
    report._read_group([],[],['kg_qty:sum','amount_usd:sum','price_per_kg:avg','shipment_count:sum'])
    assets=env['ir.asset']._get_asset_paths('web.assets_backend',{})
    assert any('step_agro_analytics/static/src/comparison.js' in str(p) for p in assets)
    if env.cr.dbname.startswith('MANAGEMENT_QA_'):
        bundle=env['ir.qweb']._get_asset_bundle('web.assets_backend')
        bundle.css(); bundle.js()
        assert not bundle.css_errors,bundle.css_errors
    print('MANAGEMENT_REGISTRY_OK '+json.dumps({'tickets':[97,98,99],'versions':EXPECTED,'views':True,'menus':True,'comparisons':True,'assets':True}))
finally:
    env.cr.rollback()
