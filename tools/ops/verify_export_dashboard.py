"""T96 read-only effective dashboard and analytical flow probe, rolled back."""
import importlib, json
from pathlib import Path
from odoo.addons.step_export_dashboard.tests.test_dashboard import DashboardCase
try:
    for name, version in EXPECTED.items():
        module = env['ir.module.module'].search([('name', '=', name)])
        assert module.state == 'installed' and module.latest_version == version
        assert Path(importlib.import_module('odoo.addons.' + name).__file__).resolve().parent == Path(ROOT) / name
    case = DashboardCase('test_weighted_totals_and_intersecting_filters'); case.env = env; case.cr = env.cr
    for method in ('test_weighted_totals_and_intersecting_filters', 'test_versions_draft_and_missing_dates', 'test_company_scope_and_invalid_filter', 'test_posted_invoice_debit_credit_and_currency'):
        getattr(case, method)()
        env.cr.rollback(); env.registry.clear_cache(); case.env = env
    menu = env.ref('step_export.menu_step_export_dashboard')
    assert menu.active and menu.action.tag == 'step_export.dashboard'
    assets = env['ir.asset']._get_asset_paths('web.assets_backend', {})
    assert any('step_export_dashboard/static/src/dashboard.js' in str(path) for path in assets)
    assert any('step_export_dashboard/static/src/dashboard.scss' in str(path) for path in assets)
    print('MANAGEMENT_REGISTRY_OK ' + json.dumps({'ticket':96,'versions':EXPECTED,'cases':4,'menu':True,'assets':True,'company_scope':True,'actual_formula':'invoice+debit-credit'}))
finally:
    env.cr.rollback()
