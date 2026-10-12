"""Check T74-T75 runtime, effective forms, master dependencies and real version flow."""
import importlib,json
from pathlib import Path
from types import SimpleNamespace
from lxml import etree
from odoo.tests.common import new_test_user
from odoo.addons.step_producer_estimate_revision.tests.test_revision import EstimateRevisionCase

try:
    for name,version in EXPECTED.items():
        module=env['ir.module.module'].search([('name','=',name)])
        assert module.state=='installed' and module.latest_version==version
        assert Path(importlib.import_module('odoo.addons.'+name).__file__).resolve().parent==Path(ROOT)/name
    company=env['res.company'].search([('vat','=','76943293-0')],limit=1) or env.company
    env=env(context=dict(env.context,allowed_company_ids=company.ids,no_reset_password=True,
                        tracking_disable=True,mail_create_nosubscribe=True))
    # Check every historical line after installation, not just new examples.
    for line in env['step.export.estimate.line'].search([]):
        process=line.export_kg/line.export_percentage if line.delivery_kind=='process' and line.export_percentage>0 else 0
        capacity=line.package_type_id.step_export_boxes_per_pallet
        group=line.package_type_id.fruit_package_group
        expected={'bin_qty':process/capacity if group=='bins' and capacity>0 else 0,
            'process_pallet_qty':process/capacity if group=='pallet' and capacity>0 else 0,
            'export_box_qty':line.export_kg/line.species_id.kg_caja if line.species_id.kg_caja>0 else 0,
            'export_pallet_qty':line.export_kg/line.species_id.base_boxes_per_pallet if line.species_id.base_boxes_per_pallet>0 else 0}
        assert all(abs(line[n]-value)<1e-6 for n,value in expected.items()),'Historical derived quantity incorrect'
    user=new_test_user(env,login='qa-t74-t75-reader',groups='stock.group_stock_manager',company_id=company.id,company_ids=[(6,0,company.ids)])
    visible=env['ir.ui.menu'].with_user(user)._visible_menu_ids()
    action=env.ref('step_export.action_step_export_package_type')
    for key in ('packing','producer'):
        menu=env.ref('step_producer_estimate_revision.'+key+'_package_types')
        assert menu.id in visible and menu.action==action
    for xmlid in ('step_export.view_step_export_package_type_form','stock.stock_package_type_form'):
        arch=etree.fromstring(env['stock.package.type'].with_user(user).get_view(view_id=env.ref(xmlid).id,view_type='form')['arch'].encode())
        assert all(arch.xpath('.//field[@name="%s"]'%n) for n in ('fruit_package_group','pallets_per_aircraft','step_export_boxes_per_pallet'))
    assert env['stock.package.type']._fields['step_export_boxes_per_pallet'].string=='Cajas por pallet/bins'
    results={}
    for group in ('bins','pallet','floor'):
        estimate=EstimateRevisionCase.sample(SimpleNamespace(env=env),group=group)
        line=estimate.estimate_line_ids
        assert line.export_box_qty==20000 and line.export_pallet_qty==500
        assert abs(line.bin_qty-(125000/35 if group=='bins' else 0))<1e-6
        assert abs(line.process_pallet_qty-(125000/35 if group=='pallet' else 0))<1e-6
        env.flush_all()
        report=env['step.producer.estimate.report'].with_user(user).search([('line_id','=',line.id)])
        assert len(report)==2
        for n in ('bin_qty','process_pallet_qty','export_box_qty','export_pallet_qty'):
            assert abs(sum(report.mapped(n))-line[n])<1e-6
        for vtype in ('list','pivot'):
            arch=etree.fromstring(report.get_view(view_id=env.ref('step_producer_estimate_report.report_'+vtype).id,view_type=vtype)['arch'].encode())
            assert arch.xpath('.//field[@name="process_pallet_qty"]')
        estimate.action_validate_estimate();estimate.action_activate_estimate()
        new=env['step.export.estimate'].browse(estimate.action_new_estimate_version()['res_id'])
        new.action_validate_estimate();new.action_activate_estimate()
        assert estimate.state=='replaced' and new.state=='current'
        results[group]={'bins':line.bin_qty,'process_pallets':line.process_pallet_qty,'export_boxes':line.export_box_qty,'export_pallets':line.export_pallet_qty}
    print('MANAGEMENT_REGISTRY_OK '+json.dumps({'tickets':[74,75],'versions':EXPECTED,'menus':True,
        'forms':True,'historical_formulas':True,'weekly_report':True,'version_flow':True,'groups':results,'package_action':action.id}))
finally:
    env.cr.rollback()
