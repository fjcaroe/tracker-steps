"""T77 exact installed source, seasonal quantities and the approved budget flow."""
import importlib,json
from pathlib import Path
from types import SimpleNamespace
from lxml import etree
from odoo import Command
from odoo.tests.common import new_test_user
from odoo.tools.safe_eval import safe_eval
from odoo.addons.step_budget_design.tests.test_design import BudgetDesignCase, save_general_budget_form

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
    assert '2026-09' in template.quantities_matrix and '2027-08' in template.values_matrix
    budget=budget.with_user(user);budget.action_generate_lines();budget.action_approve()
    assert budget.total_amount==1800000 and budget.line_ids.quantity==60 and str(budget.line_ids.month_ids.period_date)=='2026-09-01'
    revision=env[budget._name].browse(budget.action_new_revision()['res_id'])
    assert revision.season_id==budget.season_id and revision.line_ids.month_ids.period_date==budget.line_ids.month_ids.period_date
    env.flush_all()
    summary=env['step.management.budget.summary.report'].search([('budget_id','=',budget.id)])
    assert summary.hectares==4 and summary.cost_per_ha==450000
    menu=env.ref('step_management_costs.menu_operational_budget_general')
    assert menu.id in visible and menu.action==env.ref('step_management_costs.action_operational_budget_general')
    general_model=env[budget._name].with_user(user)
    form=etree.fromstring(general_model.get_view(
        view_id=env.ref('step_management_costs.view_operational_budget_form').id,
        view_type='form',
    )['arch'].encode())
    assert form.xpath('.//button[@name="action_prepare_general"]')
    assert form.xpath('.//field[@name="line_ids"]//field[@name="month_ids"]//field[@name="period_date"]')
    general=save_general_budget_form(env(user=user),template,budget)
    line=general.line_ids.filtered(lambda row: row.quantity==84)
    assert line.monthly_quantity==84 and line.amount==line.monthly_amount==2100000
    assert general.total_amount==2500000 and general.incomplete_line_count==0

    detail = form.xpath('.//field[@name="line_ids"]/form')[0]
    product_field = detail.xpath('.//field[@name="activity_id"]/following-sibling::*[1][@name="product_id"]')[0]
    assert not detail.xpath('.//field[@name="activity"]')
    catalog_menu = env.ref('step_budget_design.activity_catalog_menu')
    catalog_action = env.ref('step_budget_design.activity_catalog_action')
    assert catalog_menu.id in visible and catalog_menu.action == catalog_action
    action = catalog_action.with_user(user).run()
    assert action['res_model'] == 'account.analytic.account'
    catalog = env[action['res_model']].with_user(user)
    catalog_domain = safe_eval(action['domain'])
    activity = template.line_ids.activity_id
    assert activity.id in catalog.search(catalog_domain).ids
    assert budget.allocation_ids.center_id.id not in catalog.search(catalog_domain).ids
    assert action['context']['default_plan_id'] == activity.plan_id.id
    catalog_view = catalog.get_view(view_id=env.ref('step_budget_design.activity_catalog_form').id,
                                    view_type='form')
    assert etree.fromstring(catalog_view['arch'].encode()).xpath('.//field[@name="plan_id"][@readonly="True"]')
    added = catalog.with_context(**action['context']).web_save({'name': 'QA T225 Actividad'}, {'name': {}})
    activity = catalog.browse(added[0]['id'])
    assert activity.sudo().plan_id.id == action['context']['default_plan_id']

    product = template.line_ids.product_id
    product.management_budget_group_id = line.group_id
    wrong_group = env['step.management.budget.group'].create({
        'name': 'QA T225 otro grupo', 'code': 'QA-T225-%s' % general.id,
    })
    wrong_product = env['product.product'].create({
        'name': 'QA T225 otro grupo', 'management_budget_group_id': wrong_group.id,
    })
    products = env['product.product'].with_user(user)
    domain_expr = product_field.get('domain')
    choices = dict(products.name_search(args=safe_eval(domain_expr, {'group_id': line.group_id.id})))
    assert product.id in choices and wrong_product.id not in choices
    assert not products.name_search(args=safe_eval(domain_expr, {'group_id': False}))
    editing = line.new({'group_id': wrong_group.id, 'product_id': product.id})
    editing._onchange_group_product()
    assert not editing.product_id
    line.activity = 'QA texto histórico'
    general.web_save({'line_ids': [Command.update(line.id, {
        'product_id': product.id, 'activity_id': activity.id,
    })]}, {'line_ids': {'fields': {'product_id': {}, 'activity_id': {}}}})
    assert line.product_id == product and line.activity_id == activity and line.activity == 'QA texto histórico'

    general.action_prepare_general()
    general.action_approve()
    assert general.state=='approved'
    print('MANAGEMENT_REGISTRY_OK '+json.dumps({
        'tickets': [77, 224, 225], 'versions': EXPECTED, 'menus': True, 'forms': True,
        'pruning_formula': True, 'hectare_scaling': True, 'approval_revision': True,
        'summary': True, 'real_season_months': True, 'general_form_save': True,
        'detail_product_group': True, 'activity_catalog': True, 'legacy_activity_preserved': True,
    }))
finally:
    env.cr.rollback()
