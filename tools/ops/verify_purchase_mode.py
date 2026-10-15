"""Exercise original menus, effective forms, live grouped reports and commercial revisions."""
import importlib,json
from pathlib import Path
from odoo.addons.step_producer_purchase_mode.tests.test_purchase_mode import PurchaseModeCase
try:
    for name,version in EXPECTED.items():
        module=env['ir.module.module'].search([('name','=',name)])
        assert module.state=='installed' and module.latest_version==version
        assert Path(importlib.import_module('odoo.addons.'+name).__file__).resolve().parent==Path(ROOT)/name
    env=env(context=dict(env.context,tracking_disable=True,no_reset_password=True,mail_create_nosubscribe=True))
    # The same meaningful functional cases also run against the installed destination, rolled back.
    case=PurchaseModeCase('test_contract_modes_report_and_revision')
    case.env=env
    for name in ('test_contract_modes_report_and_revision','test_estimate_modes_report_and_version',
                 'test_forms_reports_and_company_rules','test_history_can_be_classified_without_repricing'):
        getattr(case,name)()
    print('MANAGEMENT_REGISTRY_OK '+json.dumps({'ticket_id':86,'versions':EXPECTED,'forms':True,
        'menus':True,'live_reports':True,'mode_grouping':True,'revisions':True,'no_repricing':True,'company_security':True}))
finally:
    env.cr.rollback()
