"""Verify T175 versions, real effective UI and copy-only native advance flow."""
import json
import hashlib
from pathlib import Path

from odoo.modules.module import get_module_path
from native_business_profile import scoped_business_environment
from producer_advance_checks import verify_ui, verify_advances, verify_reported_dates

try:
    for name, version in EXPECTED.items():
        module=env['ir.module.module'].search([('name','=',name),('state','=','installed')])
        assert module.latest_version==version
        assert Path(get_module_path(name)).resolve()==Path(ROOT)/name
    business=scoped_business_environment(env)
    ui=verify_ui(business)
    flow=verify_advances(env,OUTPUT) if env.cr.dbname.startswith('MANAGEMENT_QA_') else None
    plan_path=Path(OUTPUT)/'t175-date-case.json'
    reported=None
    if plan_path.is_file():
        assert env.cr.dbname=='CERRO_EL_PLOMO' or env.cr.dbname.startswith('MANAGEMENT_QA_CERRO_')
        plan_bytes=plan_path.read_bytes()
        reported=verify_reported_dates(env,json.loads(plan_bytes),run_flow=flow is not None)
        reported['plan_sha256']=hashlib.sha256(plan_bytes).hexdigest()
    print('MANAGEMENT_REGISTRY_OK '+json.dumps({'ticket':175,'versions':EXPECTED,
        'existing_profile':business.uid,'ui':ui,'copy_flow':flow,'reported_dates':reported,'live_business_writes':False}))
finally:
    env.cr.rollback()
