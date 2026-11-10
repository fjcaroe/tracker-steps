import json
from pathlib import Path

from native_business_profile import scoped_business_environment


try:
    module, version = next(iter(EXPECTED.items()))
    assert module == 'step_activities_dashboard_periods'
    installed = env['ir.module.module'].search([('name', '=', module), ('state', '=', 'installed')])
    assert installed.latest_version == version
    assets = env['ir.asset']._get_asset_paths('web.assets_backend', {})
    for filename in ('dashboard.js', 'dashboard.xml'):
        assert any(f'{module}/static/src/{filename}' in str(item) for item in assets)
        assert (Path(ROOT) / module / 'static' / 'src' / filename).is_file()
    scoped = scoped_business_environment(env)
    menu = scoped.ref('step_hr.menu_step_activities_dashboard')
    assert menu.id in scoped['ir.ui.menu']._visible_menu_ids()
    assert menu.action.tag == 'step_hr.activities_dashboard'
    for period in ('day', 'week', 'month', 'season'):
        data = scoped['hr.salary.custom'].get_activities_period_dashboard(period)
        assert data['period'] == period and data['period_label']
        metrics = data['kpis']
        assert metrics['total_cost'] == metrics['company_cost'] + metrics['contractor_cost']
    if env.cr.dbname.startswith('MANAGEMENT_QA_'):
        env['ir.qweb']._get_asset_bundle('web.assets_backend').js()
    print('MANAGEMENT_REGISTRY_OK ' + json.dumps({'ticket': 187, 'version': version, 'periods': 4, 'assets': True}))
finally:
    env.cr.rollback()
