"""T91 native shipment to guide to packing list, isolated and rolled back."""
import importlib,json
from pathlib import Path
from odoo.addons.step_packing_dispatch.tests.test_dispatch import DispatchCase
try:
    for name,version in EXPECTED.items():
        m=env['ir.module.module'].search([('name','=',name)])
        assert m.state=='installed' and m.latest_version==version
        assert Path(importlib.import_module('odoo.addons.'+name).__file__).resolve().parent==Path(ROOT)/name
    env=env(context=dict(env.context,tracking_disable=True,mail_create_nosubscribe=True,no_reset_password=True))
    case=DispatchCase('test_instruction_totals_and_source_preservation');case.env=env;case.cr=env.cr
    tests=('test_instruction_totals_and_source_preservation','test_scan_selection_guide_and_packing_list',
        'test_filters_capacity_and_duplicate_guides','test_company_access_and_native_inspection_menus')
    for method in tests:
        getattr(case,method)()
        env.cr.rollback();env.registry.clear_cache()
    for model,xmlid,keys in [('step.export.dispatch.order','step_packing_dispatch.instruction_form',('load_line_ids','pallets_per_truck','shipment_id')),
        ('step.dispatch.guide','step_dispatch_guide.view_dispatch_guide_form',('dispatch_instruction_id','load_tag_ids','scan_code')),
        ('step.export.packing.list','step_export.view_export_packing_list_form',('guide_has_dispatch_instruction',))]:
        view=env[model].get_view(env.ref(xmlid).id,'form')['arch']
        assert all(k in view for k in keys)
    print('MANAGEMENT_REGISTRY_OK '+json.dumps({'ticket':91,'versions':EXPECTED,'cases':4,'forms':True,'menus':True,
        'scanner':True,'native_guides_and_packing_lists':True,'company_access':True,'preserves_inventory':True}))
finally:env.cr.rollback()
