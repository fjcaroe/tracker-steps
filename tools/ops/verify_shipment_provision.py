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
    assert all(arch.xpath('.//field[@name="%s"]'%n) for n in ('season_analytic_account_id','species_analytic_account_id','shipment_analytic_account_id','entry_amount_clp','entry_amount_usd'))
    assert arch.xpath('.//button[@name="action_previous_state"]')
    assert record.amount_clp==90000 and record.amount_usd==100
    record.line_ids.entry_amount_clp=180000
    assert record.line_ids.currency_id==record.clp_currency_id and record.line_ids.amount_currency==180000
    record.line_ids.entry_amount_usd=100
    assert record.line_ids.currency_id==record.usd_currency_id and record.line_ids.amount_currency==100
    account=record.shipment_analytic_account_id
    record.shipment_id.provision_analytic_account_id=False
    record.action_validate();record.action_previous_state()
    assert record.state=='created'
    record.shipment_analytic_account_id=account
    record.action_validate();record.action_cost();record.action_previous_state()
    assert record.state=='validated' and not record.line_ids.expense_account_id
    record.action_previous_state()
    record.action_validate();record.action_cost();record.action_account()
    assert record.state=='posted' and record.move_id.state=='posted'
    assert abs(sum(record.move_id.line_ids.mapped('debit'))-90000)<1e-6 and abs(sum(record.move_id.line_ids.mapped('balance')))<1e-6
    analytic=record.move_id.line_ids.filtered(lambda l:l.debit).analytic_line_ids
    assert len(analytic)==1 and analytic.amount==-90000
    for account in record.season_id.cost_id | record.species_id.cost_id | record.shipment_id.provision_analytic_account_id:
        assert analytic[account.root_plan_id._column_name()]==account
    original=record.move_id;record.action_account();assert record.move_id==original
    print('MANAGEMENT_REGISTRY_OK '+json.dumps({'ticket':82,'versions':EXPECTED,'menus':True,'forms':True,'new_form_onchange':True,'preview_conversion':True,'manual_clp_usd':True,'previous_state':True,'analytic_selector':True,'posting':True,'balanced':True,'daily_rate':True,'three_analytic_plans':True,'duplicate_prevented':True}))
finally:
    env.cr.rollback()
