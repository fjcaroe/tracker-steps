"""Effective native T103 forms, smart buttons, identities and access checks."""
import importlib
import json
from pathlib import Path
from lxml import etree
from odoo.addons.step_agriculture_records.schema import MODELS, TAG_STATE_POLICY
from odoo.addons.step_agriculture_records.models.cost_center import ACTIVITIES

try:
    for name, version in EXPECTED.items():
        module = env['ir.module.module'].search([('name', '=', name)])
        assert module.state == 'installed' and module.latest_version == version
        assert Path(importlib.import_module('odoo.addons.' + name).__file__).resolve().parent == Path(ROOT) / name
    for old, model in MODELS.items():
        assert old not in env, ('Legacy runtime model remains', old)
        meta = env['ir.model'].search([('model', '=', model)])
        assert meta.state == 'base'
        assert not env['ir.model.fields'].search_count([('model', '=', model), ('state', '=', 'manual')])
        assert not any(name.startswith('x_') for name in env[model]._fields)
        key = model.removeprefix('step.agriculture.').replace('.', '_')
        for kind in ('form', 'list', 'search', 'graph', 'pivot'):
            view = env.ref('step_agriculture_records.view_' + key + '_' + kind)
            assert view.active and env[model].get_view(view_id=view.id, view_type=kind)['arch']
        env[model].with_context(active_test=False).search([], limit=5).web_read({'name': {}})
    analytic = env['account.analytic.account']
    arch = etree.fromstring(analytic.get_view(
        view_id=env.ref('step_hr.step_view_account_analytic_account_form').id, view_type='form')['arch'])
    assert len(arch.xpath("//button[@name='action_agriculture_activity']")) == 13
    assert not arch.xpath("//button/field[starts-with(@name,'x_')]")
    center = analytic.search([], limit=1)
    assert center
    for key, (_, model, relation) in ACTIVITIES.items():
        action = center.with_context(agriculture_activity=key).action_agriculture_activity()
        assert action['res_model'] == model and action['domain'] == [(relation, '=', center.id)]
        assert center['agriculture_' + key + '_count'] == env[model].search_count(action['domain'])
    if env.cr.dbname == 'LAB_TAREAS':
        assert TAG_STATE_POLICY is not None, 'An unresolved draft cannot be delivered'
    print('MANAGEMENT_REGISTRY_OK ' + json.dumps({'ticket': 103, 'versions': EXPECTED,
          'native_models': len(MODELS), 'smart_buttons': 13,
          'tag_state_policy_resolved': TAG_STATE_POLICY is not None,
          'native_forms': True, 'related_records_read': True}))
finally:
    env.cr.rollback()
