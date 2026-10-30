"""T141: native delivery action, existing profile, read-only output and PDF clone proof."""
import importlib
import json
from pathlib import Path
from lxml import etree, html
from odoo.tools import config
from native_business_profile import scoped_business_environment

try:
    for name, version in EXPECTED.items():
        module=env['ir.module.module'].search([('name','=',name)])
        assert module.state=='installed' and module.latest_version==version
        assert Path(importlib.import_module('odoo.addons.'+name).__file__).resolve().parent==Path(ROOT)/name
    scoped=scoped_business_environment(env)
    scoped=scoped(context=dict(scoped.context,lang=scoped.user.lang or 'en_US'))
    action=scoped.ref('stock.action_report_delivery')
    assert action.model=='stock.picking' and action.report_name=='stock.report_deliveryslip'
    assert action.report_type=='qweb-pdf' and action.binding_model_id.model=='stock.picking'
    assert not action.attachment_use
    menu=scoped.ref('step_packing_operations.menu_packing_reception_process')
    assert menu.id in scoped['ir.ui.menu']._visible_menu_ids()
    form=scoped.ref('step_packing_reception_revision.view_process_reception_form')
    arch=etree.fromstring(scoped['stock.picking'].get_view(view_id=form.id,view_type='form')['arch'])
    assert arch.xpath("//field[@name='fruit_guide_number']")
    previous=config['test_enable'];config['test_enable']=True
    try:
        from odoo.tests import Form
    finally:
        config['test_enable']=previous
    record=scoped['stock.picking'].search([('step_fruit_reception_kind','in',['process','packed']),('picking_type_code','=','incoming')],limit=1)
    assert record, 'A destination receipt is required for the native existing-profile verification'
    Form(record,view=form)
    content=scoped['ir.actions.report']._render_qweb_html('stock.action_report_delivery',record.ids)[0]
    assert 'RECIBO DE RECEPCIÓN' in content.decode()
    heading=html.fromstring(content).xpath("//div[contains(@class,'page')]/h2")[0].text_content()
    assert ' '.join(heading.split()) == 'RECIBO DE RECEPCIÓN N° '+record.name
    assert html.fromstring(content).xpath("//table[contains(@class,'step_receipt_pallets')]")
    outputs=[]
    if env.cr.dbname.startswith('MANAGEMENT_QA_'):
        from odoo.addons.step_packing_reception_report.tests.common import receipt_fixture
        receipt=receipt_fixture(scoped)
        for label in ('short','long'):
            if label=='long':
                original=receipt.fruit_tag_line_ids[:1]
                for i in range(60):
                    original.copy({'tag_number':'QA-141-LONG-%03d'%i,'sequence':i+10})
            pdf,_=scoped['ir.actions.report']._render_qweb_pdf('stock.action_report_delivery',receipt.ids)
            assert pdf.startswith(b'%PDF') and len(pdf)>5000
            output=Path(OUTPUT)/'data'/('receipt-'+label+'.pdf');output.write_bytes(pdf);outputs.append(output.name)
        replay=Path(PROBE_TOOLS).parents[1]/'reception-replay.json'
        if 'QA-CERRO' in env.cr.dbname and replay.exists():
            plan=json.loads(replay.read_text())
            real=scoped['stock.picking'].search([('name','=',plan['picking_name'])])
            assert len(real)==1 and real._step_is_fruit_receipt()
            before=real.fruit_tag_line_ids.read(['quantity','gross_kg','tare_kg','kilos','write_date'])
            totals=real._step_receipt_totals()
            for key,value in plan['totals'].items():
                assert abs(totals[key]-value)<0.000001,key
            pdf,_=scoped['ir.actions.report']._render_qweb_pdf('stock.action_report_delivery',real.ids)
            assert pdf.startswith(b'%PDF')
            output=Path(OUTPUT)/'data'/'receipt-reported.pdf';output.write_bytes(pdf);outputs.append(output.name)
            assert real.fruit_tag_line_ids.read(['quantity','gross_kg','tare_kg','kilos','write_date'])==before
            print('T141_REPORTED_RECEIPT_PDF_OK weights_unchanged=True')
        print('T141_NATIVE_PDF_OK '+json.dumps(outputs))
    print('MANAGEMENT_REGISTRY_OK '+json.dumps({'ticket':141,'versions':EXPECTED,'existing_profile':scoped.uid,
        'company_id':scoped.company.id,'native_menu_and_form':True,'native_print_action':True,
        'writes':False,'clone_pdfs':outputs}))
finally:
    env.cr.rollback()
