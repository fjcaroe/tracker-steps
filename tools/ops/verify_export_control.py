"""Verify T89/T90 installed package, real views and isolated end-to-end cases."""
import importlib,json
from pathlib import Path
from odoo.addons.step_export_control.tests.test_control import ExportControlCase

try:
    for name,version in EXPECTED.items():
        module=env['ir.module.module'].search([('name','=',name)])
        assert module.state=='installed' and module.latest_version==version
        assert Path(importlib.import_module('odoo.addons.'+name).__file__).resolve().parent==Path(ROOT)/name
    env=env(context=dict(env.context,tracking_disable=True,mail_create_nosubscribe=True,no_reset_password=True))
    case=ExportControlCase('test_document_deadlines_manual_and_legacy_preservation')
    case.env=env;case.cr=env.cr
    tests=('test_document_deadlines_manual_and_legacy_preservation','test_only_successful_attached_email_marks_delivery',
           'test_voyage_dates_alert_boundaries_and_routes','test_ais_validation_identity_age_and_company_access')
    for test in tests:
        getattr(case,test)()
        env.cr.rollback();env.registry.clear_cache()
    form=env['step.export.export'].get_view(env.ref('step_export.view_step_export_export_form').id,'form')['arch']
    assert all(field in form for field in ('control_documents','sent_on','transit_time','sea_route_id'))
    for xmlid,tag in [('documents_menu','step_export_control.documents'),('vessels_menu','step_export_control.vessels')]:
        menu=env.ref('step_export_control.'+xmlid)
        assert menu.active and menu.action.tag==tag
    assert env['step.export.document.type'].search_count([])==12
    for mode in ('documents','vessels'):
        data=env['step.export.export'].control_dashboard(mode=mode)
        assert len(data['types'])==12 and data['total']>=len(data['rows'])
    print('MANAGEMENT_REGISTRY_OK '+json.dumps({'tickets':[89,90],'versions':EXPECTED,'forms':True,'menus':True,
        'cases':len(tests),'native_documents_preserved':True,'successful_mail_only':True,
        'company_rules':True,'voyage_dates_and_routes':True,'ais_timestamp_validation':True}))
finally:
    env.cr.rollback()
