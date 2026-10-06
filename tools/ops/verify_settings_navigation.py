"""Verify actual settings menu actions and compiled views without reading secrets."""
import importlib
import json
from lxml import etree
from odoo.tools.safe_eval import safe_eval

try:
    for name, version in EXPECTED.items():
        module = env['ir.module.module'].search([('name', '=', name)])
        assert module.state == 'installed' and module.latest_version == version
        assert importlib.import_module('odoo.addons.' + name).__file__.startswith(ROOT + '/')
    standard = env.ref('base.res_config_settings_view_form')
    settings = env['res.config.settings']
    assert settings.get_view(view_type='form')['id'] == standard.id
    specific = env.ref('step_account_treasury_batch.view_treasury_batch_approval_settings_form')
    treasury = env.ref('step_account_treasury_batch.action_treasury_batch_approval_settings')
    assert treasury.view_id == specific and treasury.target == 'new'
    assert specific.priority > standard.priority
    assert 'treasury_batch_approval_threshold' in settings.get_view(view_id=specific.id, view_type='form')['arch']
    dispatch = env.ref('step_dispatch_guide.menu_dispatch_settings')
    assert dispatch.action == env.ref('step_dispatch_guide.action_dispatch_settings')
    assert safe_eval(dispatch.action.context)['module'] == 'step_dispatch_guide'
    checks = []
    for menu in env['ir.ui.menu'].search([('active', '=', True)]):
        action = menu.action
        if not action or action._name != 'ir.actions.act_window' or action.res_model != 'res.config.settings' or action == treasury:
            continue
        context = safe_eval(action.context or '{}')
        form_id = next((view for view, kind in action.views if kind == 'form'), False)
        view = settings.with_context(**context).get_view(view_id=form_id, view_type='form')
        arch = etree.fromstring(view['arch'])
        assert arch.get('js_class') == 'base_settings', (menu.id, view['id'])
        app = context.get('module')
        if app:
            assert arch.xpath('//app[@name=$name]', name=app), (menu.id, app)
        checks.append({'menu': menu.id, 'action': action.id, 'view': view['id'], 'section': app})
    assert len(checks) >= 20
    print('MANAGEMENT_REGISTRY_OK ' + json.dumps({'database': env.cr.dbname, 'settings_navigation': checks,
          'treasury_dialog_preserved': True, 'versions': EXPECTED}))
finally:
    env.cr.rollback()
