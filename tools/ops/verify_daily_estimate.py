"""T78: installed source, roles/forms and full daily planning/version flow."""
import importlib, json
from pathlib import Path
from types import SimpleNamespace
from lxml import etree
from odoo.tests.common import new_test_user
from odoo.addons.step_producer_daily_estimate.tests.test_daily import DailyCase

try:
    for name,version in EXPECTED.items():
        module=env['ir.module.module'].search([('name','=',name)])
        assert module.state=='installed' and module.latest_version==version
        assert Path(importlib.import_module('odoo.addons.'+name).__file__).resolve().parent==Path(ROOT)/name
    env=env(context=dict(env.context,no_reset_password=True,tracking_disable=True,mail_create_nosubscribe=True))
    user=new_test_user(env,login='qa-t78-live-planner',groups='stock.group_stock_manager')
    visible=env['ir.ui.menu'].with_user(user)._visible_menu_ids()
    for key in ('producer_markets','packing_markets','export_markets','daily_menu','wizard_menu'):
        assert env.ref('step_producer_daily_estimate.'+key).id in visible
    arch=etree.fromstring(env['step.export.estimate'].with_user(user).get_view(view_id=env.ref('step_producers.view_step_export_estimate_form').id,view_type='form')['arch'].encode())
    assert all(arch.xpath('.//field[@name="%s"]'%n) for n in ('approved_by_id','fruit_type','market_id','week_number'))
    for days in (5,6,7):
        estimate,wizard,rows=DailyCase.sample(SimpleNamespace(env=env),days)
        rows.unlink()
        wizard.with_user(user).action_distribute()
        rows=env['step.export.estimate.day'].with_user(user).search([('estimate_id','=',estimate.id)])
        assert len(rows)==2*days and abs(sum(rows.mapped('export_kg'))-100000)<1e-6 and abs(sum(rows.mapped('process_kg'))-125000)<1e-6
        rows[0].write({'process_kg':1,'export_kg':2})
        before=rows.read(['process_kg','export_kg']);wizard.action_distribute()
        assert rows.read(['process_kg','export_kg'])==before
        new=env['step.export.estimate'].browse(estimate.action_new_estimate_version()['res_id'])
        assert new.fruit_type=='organic' and new.estimate_line_ids.market_id==estimate.estimate_line_ids.market_id
        new.action_validate_estimate();new.action_activate_estimate()
        assert set(rows.mapped('state'))=={'replaced'}
    print('MANAGEMENT_REGISTRY_OK '+json.dumps({'ticket':78,'versions':EXPECTED,'menus':True,'forms':True,'daily_5_6_7':True,'manual_preserved':True,'versions_preserved':True}))
finally:
    env.cr.rollback()
