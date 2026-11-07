"""Verify T175 versions, real effective UI and copy-only native advance flow."""
import json
from pathlib import Path

from odoo.modules.module import get_module_path
from native_business_profile import scoped_business_environment
from producer_advance_checks import verify_ui, verify_advances

try:
    for name, version in EXPECTED.items():
        module=env['ir.module.module'].search([('name','=',name),('state','=','installed')])
        assert module.latest_version==version
        assert Path(get_module_path(name)).resolve()==Path(ROOT)/name
    business=scoped_business_environment(env)
    ui=verify_ui(business)
    flow=verify_advances(env,OUTPUT) if env.cr.dbname.startswith('MANAGEMENT_QA_') else None
    print('MANAGEMENT_REGISTRY_OK '+json.dumps({'ticket':175,'versions':EXPECTED,
        'existing_profile':business.uid,'ui':ui,'copy_flow':flow,'live_business_writes':False}))
finally:
    env.cr.rollback()
