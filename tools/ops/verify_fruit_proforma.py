"""T171 effective UI and rollback-only native monthly proforma smoke proof.

The publisher supplies env, ROOT, EXPECTED and OUTPUT. Production validation is
read-only. The complete 33/46 cycle runs only in a disposable MANAGEMENT_QA copy;
its temporary companies, users and documents are always rolled back.
"""
import importlib
import json
from pathlib import Path

from lxml import etree

from native_business_profile import scoped_business_environment


from fruit_proforma_checks import verify_ui, verify_copy_cycle

try:
    for module_name, version in EXPECTED.items():
        module = env['ir.module.module'].search([('name', '=', module_name)])
        assert module.state == 'installed' and module.latest_version == version
        actual = Path(importlib.import_module('odoo.addons.' + module_name).__file__).resolve().parent
        assert actual == Path(ROOT) / module_name
    scoped = scoped_business_environment(env)
    ui = verify_ui(scoped)
    flow = verify_copy_cycle(env, OUTPUT) if env.cr.dbname.startswith('MANAGEMENT_QA_') else None
    if env.cr.dbname.startswith('MANAGEMENT_QA_CERRO_'):
        assert MONTHLY_FRUIT_PLAN, 'T171 requires the original customer draft in the fresh destination copy'
        from verify_fruit_proforma_case import verify_case
        actual_case = verify_case(env, MONTHLY_FRUIT_PLAN)
        actual_business = scoped_business_environment(env,
            company=env['res.company'].browse(MONTHLY_FRUIT_PLAN['company_id']))
        actual_pdf, actual_type = actual_business['ir.actions.report']._render_qweb_pdf(
            'step_packing_fruit_proforma.report_fruit_proforma', actual_case['proformas'])
        assert actual_type == 'pdf' and actual_pdf.startswith(b'%PDF')
        (Path(OUTPUT) / 't171-actual-proforma.pdf').write_bytes(actual_pdf)
        print('T171_ACTUAL_MONTHLY_CASE_OK ' + json.dumps(actual_case))
    print('MANAGEMENT_REGISTRY_OK ' + json.dumps({'ticket': 171, 'versions': EXPECTED,
        'existing_profile': scoped.uid, 'ui': ui, 'copy_flow': flow,
        'live_business_writes': False}))
finally:
    env.cr.rollback()
