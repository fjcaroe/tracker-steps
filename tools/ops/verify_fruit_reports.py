"""Verify shared fruit masters and real receipt reports with rolled-back samples."""
import importlib,json
from pathlib import Path
from types import SimpleNamespace
from lxml import etree
from odoo.tests.common import new_test_user
from odoo.tools.safe_eval import safe_eval
from odoo.addons.step_producer_fruit_reports.tests.test_reports import FruitReportsCase
try:
    for name,version in EXPECTED.items():
        mod=env['ir.module.module'].search([('name','=',name)])
        assert mod.state=='installed' and mod.latest_version==version
        assert Path(importlib.import_module('odoo.addons.'+name).__file__).resolve().parent==Path(ROOT)/name
    company=env['res.company'].search([('vat','=','76943293-0')],limit=1) or env.company
    env=env(context=dict(env.context,allowed_company_ids=company.ids,no_reset_password=True,tracking_disable=True,mail_create_nosubscribe=True))
    user=new_test_user(env,login='qa-t70-t72-reader',groups='stock.group_stock_manager',company_id=company.id,company_ids=[(6,0,company.ids)])
    visible=env['ir.ui.menu'].with_user(user)._visible_menu_ids()
    masters={'species':'step_hr.action_step_especie','variety_group':'step_hr.action_step_grupo_variedad','variety':'step_hr.action_step_variedad','caliber_group':'step_management_costs.action_caliber_group','caliber':'step_management_costs.action_fruit_caliber','category':'step_management_costs.action_fruit_category','quality':'step_inventory_fruit_tag.action_fruit_quality','color':'step_export_client_revision.color_action'}
    parent=env.ref('step_producer_fruit_reports.fruit_config_menu')
    assert parent.parent_id==env.ref('step_producers.menu_step_producers_config_group') and parent.id in visible
    for key,xmlid in masters.items():
        menu=env.ref('step_producer_fruit_reports.config_'+key)
        assert menu.parent_id==parent and menu.action==env.ref(xmlid) and menu.id in visible, "Master menu not visible: "+key
        env[menu.action.res_model].with_user(user).search([],limit=1)
    forms=[];actions={};totals={};ids=[]
    for kind,producer_menu in [('process','menu_producer_process_receptions'),('packed','menu_producer_packed_receptions')]:
        action=env.ref('step_producer_fruit_reports.action_'+kind);actions[kind]=action.id
        menu=env.ref('step_producer_fruit_flow.'+producer_menu);inv=env.ref('step_producer_fruit_reports.inventory_'+kind)
        assert menu.action==action and inv.action==action and inv.parent_id==env.ref('stock.menu_warehouse_report')
        assert menu.id in visible and inv.id in visible and action.view_mode=='pivot,list'
        assert env.ref('step_producer_fruit_flow.action_producer_'+kind+'_receptions').res_model=='stock.picking'
        picking=FruitReportsCase.sample(SimpleNamespace(env=env),kind=kind);ids+=picking.ids
        rows=env[action.res_model].with_user(user).search([('picking_id','=',picking.id)]+safe_eval(action.domain))
        assert len(rows)==2 and set(rows.mapped('reception_kind'))=={kind}
        for vtype in ('pivot','list','search'):
            arch=etree.fromstring(rows.get_view(view_id=env.ref('step_producer_fruit_reports.report_'+vtype).id,view_type=vtype)['arch'].encode());assert arch.tag==vtype
            if vtype=='search':assert all(arch.xpath('.//field[@name="%s"]'%n) for n in ('season_id','producer_id','fundo_id','species_id','variety_id','lot_id'))
        total=rows.read_group([('id','in',rows.ids)],['packaging_qty:sum','kilos:sum'],[])[0]
        assert total['packaging_qty']==30 and total['kilos']==150;totals[kind]={'packaging_qty':30,'kilos':150}
        assert len(rows.read_group([('id','in',rows.ids)],['packaging_qty:sum','kilos:sum'],['reception_date:week']))==1
        species=picking.fruit_species_id.with_user(user)
        form=etree.fromstring(species.get_view(view_id=env.ref('step_hr.view_step_especie_form').id,view_type='form')['arch'].encode())
        assert form.xpath('.//field[@name="sag_code"]') and form.xpath('.//field[@name="base_boxes_per_pallet"]')
        assert species.sag_code=='SAG-QA' and species.base_boxes_per_pallet==60
    allrows=env['step.fruit.reception.report'].search([('picking_id','in',ids)])
    assert len(allrows)==4 and sum(allrows.mapped('kilos'))==300
    other=env['res.company'].create({'name':'QA T70-T72 other'})
    outsider=new_test_user(env,login='qa-t70-t72-outsider',groups='stock.group_stock_user',company_id=other.id,company_ids=[(6,0,other.ids)])
    assert not env['step.fruit.reception.report'].with_user(outsider).with_context(allowed_company_ids=other.ids).search([('id','in',allrows.ids)])
    print('MANAGEMENT_REGISTRY_OK '+json.dumps({'tickets':[70,71,72],'versions':EXPECTED,'shared_masters':True,'species_form':True,'menus':True,'pivot_list_filters':True,'source_receipts_validated':True,'company_security':True,'actions':actions,'totals':totals}))
finally:
    env.cr.rollback()
