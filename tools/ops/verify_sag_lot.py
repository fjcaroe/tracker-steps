"""T93 native multi-OT lots, formats, Excel and PDF; every fixture rolls back."""
import importlib
import json
from pathlib import Path
from odoo.addons.step_packing_sag.tests.test_lot import SagLotCase

try:
    for name, version in EXPECTED.items():
        module=env['ir.module.module'].search([('name','=',name)])
        assert module.state=='installed' and module.latest_version==version
        assert Path(importlib.import_module('odoo.addons.'+name).__file__).resolve().parent==Path(ROOT)/name
    env=env(context=dict(env.context,tracking_disable=True,mail_create_nosubscribe=True,no_reset_password=True))
    tests=('test_lifecycle_pending_and_destination_dispatch_gate','test_required_evidence_sampling_treatment_and_rejection',
        'test_access_company_and_validation','test_native_internal_and_menu_form',
        'test_multi_ot_scanner_and_approval_covers_all_outputs','test_filters_reject_organic_other_variety_no_stock_and_duplicates',
        'test_five_annex5_formats_match_official_widths','test_annex_workbook_pdf_and_missing_origin')
    case=SagLotCase(tests[0]);case.env=env;case.cr=env.cr
    for test in tests:
        getattr(case,test)()
        env.cr.rollback();env.registry.clear_cache()
    if env.cr.dbname.startswith('MANAGEMENT_QA_'):
        from unittest.mock import patch
        lot, shipment = case._approved_multi()
        folder = Path('/tmp') / ('t93-reports-' + env.cr.dbname)
        folder.mkdir(mode=0o700, exist_ok=True)
        (folder/'dispatch-annex.xlsx').write_bytes(lot._sag_annex_xlsx())
        pdf, _ = env['ir.actions.report']._render_qweb_pdf('step_packing_sag.report_dispatch_annex', res_ids=lot.ids)
        (folder/'dispatch-annex.pdf').write_bytes(pdf)
        filename, data = lot._sag_flat_file()
        (folder/filename).write_bytes(data)
        # A dedicated layout-only fixture verifies per-page reference and totals.
        rows = lot._sag_annex_rows()
        with patch.object(type(lot), '_sag_annex_rows', lambda self: rows * 40):
            pdf, _ = env['ir.actions.report']._render_qweb_pdf('step_packing_sag.report_dispatch_annex', res_ids=lot.ids)
            (folder/'layout-qa-only.pdf').write_bytes(pdf)
        print('MANAGEMENT_ARTIFACTS_OK ' + str(folder))
        env.cr.rollback();env.registry.clear_cache()
    print('MANAGEMENT_REGISTRY_OK '+json.dumps({'ticket':93,'versions':EXPECTED,'cases':len(tests),
        'multi_ot':True,'scan':True,'five_formats':True,'xlsx_pdf':True,'company_access':True}))
finally:env.cr.rollback()
