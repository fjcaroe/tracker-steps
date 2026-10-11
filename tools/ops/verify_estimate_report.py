"""Native T68 report flow, effective views, menu, Gantt and pivot; rolled back."""
import importlib,json
from pathlib import Path
from types import SimpleNamespace
from lxml import etree
from odoo.tests.common import new_test_user
from odoo.addons.step_producer_estimate_report.tests.test_report import EstimateReportCase
try:
    for name,version in EXPECTED.items():
        module=env['ir.module.module'].search([('name','=',name)])
        assert module.state=='installed' and module.latest_version==version
        assert Path(importlib.import_module('odoo.addons.'+name).__file__).resolve().parent==Path(ROOT)/name
    company=env['res.company'].search([('vat','=','76943293-0')],limit=1) or env.company
    env=env(context=dict(env.context,allowed_company_ids=company.ids))
    user=new_test_user(env,login='qa-t68-report',groups='base.group_user',company_id=company.id,company_ids=[(6,0,company.ids)])
    action=env.ref('step_producer_estimate_report.report_action')
    menu=env.ref('step_producer_estimate_report.report_menu')
    assert menu.parent_id==env.ref('step_producers.menu_step_producers_planning_group') and menu.action==action
    assert menu.id in env['ir.ui.menu'].with_user(user)._visible_menu_ids()
    estimate,price=EstimateReportCase.sample(SimpleNamespace(env=env))
    estimate.action_validate_estimate();estimate.action_activate_estimate();env.flush_all()
    rows=env[action.res_model].with_user(user).search([('estimate_id','=',estimate.id),('state','=','current')])
    for kind in ('gantt','pivot','list','search'):
        arch=etree.fromstring(rows.get_view(view_id=env.ref('step_producer_estimate_report.report_'+kind).id,view_type=kind)['arch'].encode())
        assert arch.tag==kind
        if kind=='search':
            assert all(arch.xpath('.//field[@name="%s"]'%field) for field in ('season_id','species_id','variety_id','delivery_kind','producer_id'))
    totals=rows.read_group([('id','in',rows.ids)],['export_kg:sum','process_kg:sum','export_box_qty:sum','export_pallet_qty:sum','bin_qty:sum','amount_usd:sum','unvalued_week_qty:sum'],[])[0]
    assert totals['export_kg']==100 and totals['process_kg']==125 and totals['amount_usd']==200 and totals['unvalued_week_qty']==0
    gantt=rows.get_gantt_data([('id','in',rows.ids)],['producer_id'],{n:{} for n in ('display_name','producer_id','estimate_id','week_start','week_end','export_kg','amount_usd')},start_date='2026-11-01 00:00:00',stop_date='2026-12-01 00:00:00',scale='month')
    assert len(gantt['records'])==2 and sum(r['amount_usd'] for r in gantt['records'])==200
    assert len(rows.read_group([('id','in',rows.ids)],['export_kg:sum','amount_usd:sum'],['week_start:week']))==2
    other=env['res.company'].create({'name':'QA T68 live company separation'})
    outsider=new_test_user(env,login='qa-t68-outsider',groups='base.group_user',company_id=other.id,company_ids=[(6,0,other.ids)])
    assert not env[action.res_model].with_user(outsider).with_context(allowed_company_ids=other.ids).search([('id','in',rows.ids)])
    print('MANAGEMENT_REGISTRY_OK ' +json.dumps({'ticket':68,'versions':EXPECTED,'action_id':action.id,'menu_visible':True,'views':True,'gantt':True,'pivot':True,'company_security_tested':True,'quantities':totals['export_kg'],'amount_usd':totals['amount_usd']}))
finally:
    env.cr.rollback()
