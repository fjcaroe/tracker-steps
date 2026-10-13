"""T77 exact installed source, seasonal quantities and the approved budget flow."""
import importlib,json
from pathlib import Path
from types import SimpleNamespace
from lxml import etree
from odoo.tests.common import new_test_user
from odoo.addons.step_budget_design.tests.test_design import BudgetDesignCase

try:
    for name,version in EXPECTED.items():
        module=env['ir.module.module'].search([('name','=',name)])
        assert module.state=='installed' and module.latest_version==version
        assert Path(importlib.import_module('odoo.addons.'+name).__file__).resolve().parent==Path(ROOT)/name
    env=env(context=dict(env.context,no_reset_password=True,tracking_disable=True,mail_create_nosubscribe=True))
    user=new_test_user(env,login='qa-t77-live-planner',groups='step_management_costs.group_management_manager')
    visible=env['ir.ui.menu'].with_user(user)._visible_menu_ids()
    for key in ('template_import_menu','machinery_menu','data_menu','summary_menu','days_menu','center_menu','labor_menu'):
        assert env.ref('step_budget_design.'+key).id in visible
    arch=etree.fromstring(env['step.management.budget.template'].with_user(user).get_view(view_id=env.ref('step_management_costs.view_budget_template_form').id,view_type='form')['arch'].encode())
    assert all(arch.xpath('.//field[@name="%s"]'%n) for n in ('season_id','calculation_uom_id','calculation_unit_price','period_date'))
    template,budget=BudgetDesignCase.sample(SimpleNamespace(env=env))
    assert template.line_ids.calculation_quantity==15 and template.line_ids.calculation_unit_price==30000
    budget=budget.with_user(user);budget.action_generate_lines();budget.action_approve()
    assert budget.total_amount==1800000 and budget.line_ids.quantity==60 and str(budget.line_ids.month_ids.period_date)=='2026-09-01'
    revision=env[budget._name].browse(budget.action_new_revision()['res_id'])
    assert revision.season_id==budget.season_id and revision.line_ids.month_ids.period_date==budget.line_ids.month_ids.period_date
    env.flush_all()
    summary=env['step.management.budget.summary.report'].search([('budget_id','=',budget.id)])
    assert summary.hectares==4 and summary.cost_per_ha==450000
    print('MANAGEMENT_REGISTRY_OK '+json.dumps({'ticket':77,'versions':EXPECTED,'menus':True,'forms':True,'pruning_formula':True,'hectare_scaling':True,'approval_revision':True,'summary':True,'real_season_months':True}))
finally:
    env.cr.rollback()
