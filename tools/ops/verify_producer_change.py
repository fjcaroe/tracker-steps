"""Verify the installed native repacking flow with a rolled-back transaction."""
import importlib,json
from pathlib import Path
from odoo.addons.step_packing_producer_change.tests.test_producer_change import ProducerChangeCase
try:
    for name,version in EXPECTED.items():
        module=env['ir.module.module'].search([('name','=',name)])
        assert module.state=='installed' and module.latest_version==version
        assert Path(importlib.import_module('odoo.addons.'+name).__file__).resolve().parent==Path(ROOT)/name
    env=env(context=dict(env.context,tracking_disable=True,no_reset_password=True,mail_create_nosubscribe=True))
    case=ProducerChangeCase('test_change_stock_traceability_and_print')
    case.env=env
    case.cr=env.cr
    for name in ('test_change_stock_traceability_and_print','test_normal_repack_inherits_and_rejects_new_change','test_company_scope_and_effective_form'):
        getattr(case,name)()
    if '/steps-validation/' in ROOT:
        pdf,_=env['ir.actions.report']._render_qweb_pdf('step_inventory_fruit_tag.action_report_fruit_tag',case.target.ids)
        assert pdf.startswith(b'%PDF')
        (Path(ROOT).parent/'t87-tarja.pdf').write_bytes(pdf)
    print('MANAGEMENT_REGISTRY_OK '+json.dumps({'ticket_id':87,'versions':EXPECTED,'forms':True,'menus':True,'stock':True,'traceability':True,'printed_producer':True,'company_security':True}))
finally:
    env.cr.rollback()
