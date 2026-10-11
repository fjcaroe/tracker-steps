"""Verify effective T69 forms, filters, views, native Gantt/pivot and company access."""
import importlib,json
from pathlib import Path
from types import SimpleNamespace
from lxml import etree
from odoo.tests.common import new_test_user
from odoo.addons.step_producer_contract_report.tests.test_report import ContractReportCase
try:
    for name,version in EXPECTED.items():
        module=env['ir.module.module'].search([('name','=',name)])
        assert module.state=='installed' and module.latest_version==version
        assert Path(importlib.import_module('odoo.addons.'+name).__file__).resolve().parent==Path(ROOT)/name
    company=env['res.company'].search([('vat','=','76943293-0')],limit=1) or env.company
    env=env(context=dict(env.context,allowed_company_ids=company.ids))
    user=new_test_user(env,login='qa-t69-report',groups='base.group_user',company_id=company.id,company_ids=[(6,0,company.ids)])
    action=env.ref('step_producer_contract_report.report_action');menu=env.ref('step_producer_contract_report.report_menu')
    assert menu.parent_id==env.ref('step_producers.menu_step_producers_planning_group') and menu.action==action
    assert menu.id in env['ir.ui.menu'].with_user(user)._visible_menu_ids()
    contract=ContractReportCase.sample(SimpleNamespace(env=env))
    contract.action_confirm();env.flush_all()
    form=etree.fromstring(contract.with_user(user).get_view(view_type='form')['arch'].encode())
    assert form.xpath(".//field[@name='season_id']") and form.xpath(".//field[@name='installment_ids']")
    rows=env[action.res_model].with_user(user).search([('contract_id','=',contract.id)])
    for kind in ('gantt','pivot','list','search'):
        arch=etree.fromstring(rows.get_view(view_id=env.ref('step_producer_contract_report.report_'+kind).id,view_type=kind)['arch'].encode())
        assert arch.tag==kind
        if kind=='search':assert all(arch.xpath('.//field[@name="%s"]'%f) for f in ('season_id','species_id','variety_id','producer_id','contract_id'))
    totals=rows.read_group([('id','in',rows.ids)],['quantity_kg:sum','amount_usd:sum','unconverted_qty:sum','unconverted_kg_qty:sum'],[])[0]
    assert totals['quantity_kg']==100 and totals['amount_usd']==200 and totals['unconverted_qty']==0 and totals['unconverted_kg_qty']==0
    gantt=rows.get_gantt_data([('id','in',rows.ids)],['producer_id'],{n:{} for n in ('display_name','producer_id','contract_id','date_due','date_stop','quantity_kg','amount_usd')},start_date='2026-11-01 00:00:00',stop_date='2027-01-01 00:00:00',scale='month')
    assert len(gantt['records'])==2 and sum(r['amount_usd'] for r in gantt['records'])==200
    assert len(rows.read_group([('id','in',rows.ids)],['quantity_kg:sum','amount_usd:sum'],['date_due:week']))==2
    first=contract.installment_ids.sorted('date_due')[0];first.state='accounted'
    revision=contract.browse(contract.action_revise()['res_id']);revision.action_confirm();env.flush_all()
    current=env[action.res_model].with_user(user).search([('contract_id','in',(contract|revision).ids)])
    assert len(current)==2 and sum(current.mapped('amount_usd'))==200 and revision.season_id==contract.season_id
    other=env['res.company'].create({'name':'QA T69 live company separation'})
    outsider=new_test_user(env,login='qa-t69-outsider',groups='base.group_user',company_id=other.id,company_ids=[(6,0,other.ids)])
    assert not env[action.res_model].with_user(outsider).with_context(allowed_company_ids=other.ids).search([('id','in',current.ids)])
    print('MANAGEMENT_REGISTRY_OK '+json.dumps({'ticket':69,'versions':EXPECTED,'action_id':action.id,'menu_visible':True,'views':True,'gantt':True,'pivot':True,'company_security_tested':True,'season_form':True,'revision_without_duplicates':True,'quantity_kg':totals['quantity_kg'],'amount_usd':totals['amount_usd']}))
finally:
    env.cr.rollback()
