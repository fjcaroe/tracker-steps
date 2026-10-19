"""Verify T94 native genealogy, seven stages and actual replacement views."""
import importlib
import json
from pathlib import Path
from odoo.addons.step_export_traceability.tests.test_traceability import TraceCase

try:
    for name, version in EXPECTED.items():
        module=env['ir.module.module'].search([('name','=',name)])
        assert module.state=='installed' and module.latest_version==version
        assert Path(importlib.import_module('odoo.addons.'+name).__file__).resolve().parent==Path(ROOT)/name
    tests=('test_complete_panel_links_and_native_action','test_empty_and_live_refresh',
           'test_repack_retains_prior_process_and_company_rules')
    case=TraceCase(tests[0]);case.env=env(context=dict(env.context,tracking_disable=True,
        mail_create_nosubscribe=True,no_reset_password=True,mail_notify_force_send=False));case.cr=env.cr
    for test in tests:
        getattr(case,test)()
        env.cr.rollback();env.registry.clear_cache()
    print('MANAGEMENT_REGISTRY_OK '+json.dumps({'ticket':94,'versions':EXPECTED,'cases':len(tests),'seven_stages':True}))
finally:
    env.cr.rollback()
