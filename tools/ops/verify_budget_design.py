"""T77 exact installed source, seasonal quantities and the approved budget flow."""
import importlib,json
from pathlib import Path
from types import SimpleNamespace
from lxml import etree
from odoo import Command
from odoo.tests.common import new_test_user
from odoo.tools.safe_eval import safe_eval
from odoo.addons.step_budget_design.tests.test_design import BudgetDesignCase, save_general_budget_form
from odoo.addons.step_budget_design.tests.test_dashboard import dashboard_sample
from odoo.addons.step_budget_design.tests.test_actual_costs import actual_cost_sample, actual_cost_move, actual_cost_rows, exercise_booked_operational_currency
from odoo.addons.step_budget_design.models.actual_costs import default_plan, ROLE_FIELDS
from odoo.addons.step_management_estimation_entry.tests.test_entry import (
    estimation_entry_sample, exercise_estimation_entry,
)

try:
    for name,version in EXPECTED.items():
        module=env['ir.module.module'].search([('name','=',name)])
        assert module.state=='installed' and module.latest_version==version
        assert Path(importlib.import_module('odoo.addons.'+name).__file__).resolve().parent==Path(ROOT)/name
    env=env(context=dict(env.context,no_reset_password=True,tracking_disable=True,mail_create_nosubscribe=True))
    for role, field_name in ROLE_FIELDS.items():
        expected_plan = default_plan(env, role)
        if expected_plan:
            assert all(company[field_name] for company in env['res.company'].sudo().search([])), (
                'Existing companies must retain or initialize the native analytical role', role)
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
    estimate, center, other, plots = estimation_entry_sample(env)
    exercise_estimation_entry(estimate.with_user(user), center, other, plots)
    assert env.ref('step_management_costs.menu_estimation').id in visible
    company = env['res.company'].create({'name': 'QA T228 Panel', 'currency_id': env.ref('base.CLP').id})
    dashboard_env = env['res.company'].with_company(company).with_context(allowed_company_ids=company.ids).env
    dashboard = dashboard_sample(dashboard_env)
    planner = new_test_user(dashboard_env, login='qa-t228-panel-live',
        groups='step_management_costs.group_management_manager', company_id=company.id,
        company_ids=[Command.set(company.ids)])
    panel = dashboard['budget'].with_user(planner)
    result = panel.get_management_dashboard(season_id=dashboard['season'].id)
    assert result['budgets']['amount'] == 650 and result['budgets']['investment'] == 300
    assert [(row['income'], row['cost'], row['result']) for row in result['projected']] == [(1000, 500, 500), (500, 150, 350)]
    row = result['recent'][0]
    assert (row['harvest'], row['maintenance'], row['amount'], row['cost_per_ha']) == (450, 500, 950, 95)
    assert row['estimated_kg'] is None and row['cost_per_kg'] is None
    estimate = dashboard['estimate'].with_user(planner)
    estimate.action_validate()
    row = panel.get_management_dashboard(season_id=dashboard['season'].id)['recent'][0]
    assert row['estimated_kg'] == estimate.total_kg == 2000 and row['cost_per_kg'] == .475
    filtered = panel.get_management_dashboard(season_id=dashboard['season'].id, species_id=dashboard['species'][0].id)
    assert filtered['budgets']['amount'] == 500 and filtered['budgets']['investment'] == 200
    assert filtered['recent'][0]['estimated_kg'] == 1200
    dashboard_env['step.management.exchange.rate'].create({
        'currency_id': env.ref('base.USD').id, 'year': 2026, 'month': '11', 'company_value_per_unit': 1000,
    })
    converted = panel.get_management_dashboard(season_id=dashboard['season'].id, currency_id=env.ref('base.USD').id)
    assert converted['currencies']['selected'] == 'USD'
    assert abs(converted['budgets']['amount'] - .65) < 1e-9
    assert abs(converted['recent'][0]['amount'] - .95) < 1e-9
    assert not panel.get_management_dashboard(season_id=dashboard['other_season'].id)['recent']
    ledger = actual_cost_sample(dashboard_env)
    accountant = new_test_user(dashboard_env, login='qa-t229-ledger-live', company_id=company.id,
        company_ids=[Command.set(company.ids)],
        groups='step_management_costs.group_management_readonly,account.group_account_readonly')
    source_move = actual_cost_move(ledger)
    before = [(line.id,line.debit,line.credit,line.amount_currency,line.analytic_distribution) for line in source_move.line_ids]
    real_rows = actual_cost_rows(ledger, source_move, accountant)
    assert len(real_rows) == 2 and real_rows.mapped('quantity') == [4,6]
    assert sum(real_rows.mapped('debit_clp')) == 100000 and sum(real_rows.mapped('debit_usd')) == 100
    assert real_rows.season_ids == ledger['analytics'][0] and real_rows.activity_ids == ledger['analytics'][3]
    assert real_rows.group_id == ledger['group'] and real_rows.origin_id == ledger['group'].origin_id
    real_visible = env['ir.ui.menu'].with_user(accountant)._visible_menu_ids()
    real_menu = env.ref('step_budget_design.actual_costs_menu')
    assert real_menu.id in real_visible and real_menu.action.res_model == real_rows._name
    for kind in ('list','form','search'):
        view = real_rows.get_view(view_id=env.ref('step_budget_design.actual_costs_'+kind).id,view_type=kind)
        assert 'center_id' in view['arch']
    assert real_rows.action_export_excel()['target'] == 'download'
    assert real_rows[0].action_open_move()['res_id'] == source_move.id
    assert before == [(line.id,line.debit,line.credit,line.amount_currency,line.analytic_distribution) for line in source_move.line_ids]
    if 'operational_debit' in env['account.move.line']._fields:
        exercise_booked_operational_currency(ledger, accountant)
    if env.cr.dbname.startswith('MANAGEMENT_QA_') and '_t229_' in env.cr.dbname:
        preview = Path('/tmp') / ('t229-costs-'+env.cr.dbname+'.xlsx')
        preview.write_bytes(real_rows._excel_bytes())
        preview.chmod(0o600)
        print('ACTUAL_COSTS_XLSX_PROOF '+str(preview))
    print('MANAGEMENT_REGISTRY_OK '+json.dumps({
        'tickets': [77, 224, 225, 226, 227, 228, 229], 'versions': EXPECTED, 'menus': True, 'forms': True,
        'pruning_formula': True, 'hectare_scaling': True, 'approval_revision': True,
        'summary': True, 'real_season_months': True, 'general_form_save': True,
        'detail_product_group': True, 'activity_catalog': True, 'legacy_activity_preserved': True,
        'estimate_entry': True, 'estimate_filters': True, 'native_plots': True,
        'estimate_per_plot': True, 'independent_plot_yield': True,
        'dashboard_filters': True, 'investment_split': True, 'projected_result': True,
        'harvest_columns': True, 'current_estimation': True, 'currency_conversion': True,
        'actual_costs': True, 'ledger_source_unchanged': True, 'allocated_amounts': True,
        'actual_costs_excel': True, 'actual_costs_filters': True, 'native_ledger_permissions': True,
        'booked_operational_currency': True,
    }))
finally:
    env.cr.rollback()
