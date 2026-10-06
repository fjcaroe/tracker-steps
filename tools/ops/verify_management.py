"""Executed in an Odoo shell with ROOT and EXPECTED injected by the runner."""
import importlib
import json
from lxml import etree

try:
    for name, version in EXPECTED.items():
        module = env['ir.module.module'].search([('name', '=', name)])
        assert module.state == 'installed' and module.latest_version == version, (name, module.latest_version)
        assert importlib.import_module('odoo.addons.' + name).__file__.startswith(ROOT + '/'), name
    assert 'step.management.cost.center' not in env.registry.models, 'Parallel center model remains registered'
    for name in ('step.management.estimation', 'step.management.budget.line', 'step.management.historical.cost'):
        for field in ('center_id', 'center_ids'):
            if field in env[name]._fields:
                assert env[name]._fields[field].comodel_name == 'account.analytic.account', (name, field)
    action = env.ref('step_management_costs.action_cost_center')
    assert action.res_model == 'account.analytic.account'
    form_id = env.ref('step_hr.step_view_account_analytic_account_form').id
    arch = env['account.analytic.account'].get_view(view_id=form_id, view_type='form')['arch']
    for field in ('has_cost', 'especie_id', 'variedad_id', 'fundo_id'):
        assert 'name="' + field + '"' in arch, field
    menu = env.ref('step_management_costs.menu_cost_center')
    assert menu.parent_id == env.ref('step_management_costs.menu_management_control')
    estimator = env['step.management.estimation']
    for field, model in (('season_id', 'step.temporada'), ('species_id', 'step.especie'), ('variety_id', 'step.variedad')):
        assert estimator._fields[field].comodel_name == model
    effective = etree.fromstring(estimator.get_view(view_type='form')['arch'])
    for field in ('season_id', 'species_id', 'variety_id'):
        assert effective.xpath('//field[@name="%s"]' % field), field
    for field in ('season', 'species', 'variety'):
        # Nested one2many fields belong to estimation.line, not this header;
        # those snapshots have their own lifecycle and freeze checks.
        nodes=effective.xpath('//sheet/group/group/field[@name="%s"]' % field)
        assert all(node.get('invisible') in ('1', 'True') or node.get('readonly') in ('1', 'True') for node in nodes), 'Editable header text input remains: ' + field
    models = ('step.temporada', 'step.especie', 'step.variedad', 'step.grupo.variedad')
    for name in models:
        assert env[name]._fields['company_ids'].type == 'many2many'
        assert not env[name]._fields['company_id'].required
        assert 'company_ids' in env[name].get_view(view_type='form')['arch']
    if 'step_management_costs_producers' in EXPECTED:
        assert env['step.export.estimate']._fields['cost_center_id'].comodel_name == 'account.analytic.account'
    if 'step_management_costs_tracker' in EXPECTED:
        assert env['step.tracker.cost_center']._fields['management_center_id'].comodel_name == 'account.analytic.account'
        assert env['step.tracker.cost.wizard']._fields['center_id'].comodel_name == 'account.analytic.account'
        assert env['step.tracker.cost.wizard'].get_view(view_type='form')['arch']
    print('MANAGEMENT_REGISTRY_OK ' + json.dumps({'database': env.cr.dbname, 'versions': EXPECTED, 'native_centers': True, 'catalog_selectors': True, 'company_scopes': True}))
finally:
    env.cr.rollback()
