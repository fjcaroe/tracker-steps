"""T92 actual native Packing lifecycle, isolated and rolled back."""
import importlib
import json
from pathlib import Path
from odoo.addons.step_packing_sag.tests.test_sag import SagCase

try:
    for name, version in EXPECTED.items():
        module = env['ir.module.module'].search([('name', '=', name)])
        assert module.state == 'installed' and module.latest_version == version
        assert Path(importlib.import_module('odoo.addons.' + name).__file__).resolve().parent == Path(ROOT) / name
    env = env(context=dict(env.context, tracking_disable=True, mail_create_nosubscribe=True, no_reset_password=True))
    case = SagCase('test_native_internal_and_menu_form')
    case.env = env
    case.cr = env.cr
    tests = ('test_lifecycle_pending_and_destination_dispatch_gate',
             'test_required_evidence_sampling_treatment_and_rejection',
             'test_access_company_and_validation', 'test_native_internal_and_menu_form')
    for method in tests:
        getattr(case, method)()
        env.cr.rollback()
        env.registry.clear_cache()
    print('MANAGEMENT_REGISTRY_OK ' + json.dumps({'ticket': 92, 'versions': EXPECTED,
        'cases': len(tests), 'native_closed_ot': True, 'external_evidence': True,
        'pending_blocks_dispatch': True, 'menus': True, 'forms': True, 'company_access': True}))
finally:
    env.cr.rollback()
