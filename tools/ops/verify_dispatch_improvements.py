"""T95 real native communications, report rendering and company access, rolled back."""
import importlib, json
from pathlib import Path
from odoo.addons.step_packing_dispatch_improvements.tests.test_instruction import InstructionCase
try:
    for name, version in EXPECTED.items():
        module = env['ir.module.module'].search([('name','=',name)])
        assert module.state == 'installed' and module.latest_version == version
        assert Path(importlib.import_module('odoo.addons.'+name).__file__).resolve().parent == Path(ROOT)/name
    case = InstructionCase('test_header_source_and_guide'); case.env = env; case.cr = env.cr
    tests = ('test_header_source_and_guide', 'test_six_role_codes_and_native_communications',
             'test_reports_include_all_load_columns_and_totals', 'test_cross_company_download_denied')
    for method in tests:
        getattr(case, method)()
        env.cr.rollback(); env.registry.clear_cache()
        case.env = env
    case.fixture()
    if env.cr.dbname.startswith('MANAGEMENT_QA_'):
        short_pdf, _ = env['ir.actions.report']._render_qweb_pdf(
            'step_packing_dispatch_improvements.instruction_report', case.plan.ids)
        Path('/tmp/t95-'+env.cr.dbname+'-short.pdf').write_bytes(short_pdf)
    # Render the actual PDF engine, including multiple pages of complete load columns.
    from odoo import Command
    case.plan.load_line_ids = [Command.create({
        'product_id':case.product.id, 'packaging_id':case.packaging.id,
        'producer_id':case.producer.id, 'label':'QA T95 línea %s'%i,
        'pallet_qty':i+1, 'boxes_per_pallet':10, 'kg_per_box':5}) for i in range(80)]
    pdf, _ = env['ir.actions.report']._render_qweb_pdf(
        'step_packing_dispatch_improvements.instruction_report', case.plan.ids)
    assert pdf.startswith(b'%PDF') and len(pdf)>5000
    if env.cr.dbname.startswith('MANAGEMENT_QA_'):
        Path('/tmp/t95-'+env.cr.dbname+'.pdf').write_bytes(pdf)
        Path('/tmp/t95-'+env.cr.dbname+'.xlsx').write_bytes(case.plan._dispatch_xlsx())
    arch=env['step.export.dispatch.order'].get_view(env.ref('step_packing_dispatch.instruction_form').id,'form')['arch']
    assert all(k in arch for k in ('dus_folio','destination_country_id','destination_port_id','customs_agent_code',
        'freight_carrier_id','chatter','action_dispatch_pdf','action_dispatch_xlsx'))
    menu=env.ref('step_packing_operations.menu_packing_dispatch_order')
    assert menu.active and menu.action == env.ref('step_packing_dispatch.instructions_action')
    print('MANAGEMENT_REGISTRY_OK '+json.dumps({'ticket':95,'versions':EXPECTED,'cases':4,
        'forms':True,'menus':True,'pdf':True,'xlsx':True,'chatter':True,'company_access':True}))
finally:
    env.cr.rollback()
