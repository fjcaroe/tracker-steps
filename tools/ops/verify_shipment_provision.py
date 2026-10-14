"""T79 installed source/form/menu and actual posting using rollback-only fixtures."""
import importlib,json
from pathlib import Path
from types import SimpleNamespace
from lxml import etree
from odoo.tests.common import new_test_user
from odoo.addons.step_export_shipment_provision.tests.test_provision import ProvisionCase

try:
    for name,version in EXPECTED.items():
        module=env['ir.module.module'].search([('name','=',name)])
        assert module.state=='installed' and module.latest_version==version
        assert Path(importlib.import_module('odoo.addons.'+name).__file__).resolve().parent==Path(ROOT)/name
    # A standalone shell does not have TransactionCase's test mode. Prevent
    # Odoo from scheduling a localization install for this rollback-only
    # fixture company; posting itself runs again with normal context.
    fixture_env=env(context=dict(env.context,chart_template_load=True))
    record=ProvisionCase.sample(SimpleNamespace(env=fixture_env)).with_context(chart_template_load=False)
    user=new_test_user(record.env,login='qa-t79-live-accountant',groups='account.group_account_manager,stock.group_stock_manager',company_id=record.company_id.id,company_ids=[(6,0,record.company_id.ids)])
    record=record.with_user(user)
    assert record.env.ref('step_export_shipment_provision.provision_menu').id in record.env['ir.ui.menu']._visible_menu_ids()
    arch=etree.fromstring(record.get_view(view_id=record.env.ref('step_export_shipment_provision.provision_form').id,view_type='form')['arch'].encode())
    assert all(arch.xpath('.//field[@name="%s"]'%n) for n in ('season_id','program_id','shipment_id','journal_id','move_id'))
    blank = record.env['step.export.shipment.provision'].onchange({}, [], {
        'company_id': {}, 'state': {}, 'date': {},
        'analytic_distribution': {}, 'analytic_precision': {},
    })
    assert blank['value']['state'] == 'created' and 'analytic_precision' in blank['value']
    record.action_validate();record.action_cost();record.action_account()
    assert record.state=='posted' and record.move_id.state=='posted'
    assert abs(sum(record.move_id.line_ids.mapped('debit'))-90000)<1e-6 and abs(sum(record.move_id.line_ids.mapped('balance')))<1e-6
    analytic=record.move_id.line_ids.filtered(lambda l:l.debit).analytic_line_ids
    assert len(analytic)==1 and analytic.amount==-90000
    for account in record.season_id.cost_id | record.species_id.cost_id | record.shipment_id.provision_analytic_account_id:
        assert analytic[account.root_plan_id._column_name()]==account
    original=record.move_id;record.action_account();assert record.move_id==original
    print('MANAGEMENT_REGISTRY_OK '+json.dumps({'ticket':80,'versions':EXPECTED,'menus':True,'forms':True,'new_form_onchange':True,'posting':True,'balanced':True,'daily_rate':True,'three_analytic_plans':True,'duplicate_prevented':True}))
finally:
    env.cr.rollback()
