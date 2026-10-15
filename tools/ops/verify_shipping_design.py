"""T83 effective form, fixed sections, native PDFs and role workflow; rollback."""
import importlib, json
from pathlib import Path
from types import SimpleNamespace
from lxml import etree
from odoo.tests.common import new_test_user
from odoo.addons.step_export_shipping_design.tests.test_shipping import ShippingCase

try:
    for name, version in EXPECTED.items():
        module=env['ir.module.module'].search([('name','=',name)])
        assert module.state=='installed' and module.latest_version==version
        assert Path(importlib.import_module('odoo.addons.'+name).__file__).resolve().parent==Path(ROOT)/name
    fixture=env(context=dict(env.context,chart_template_load=True))
    shipment,order=ShippingCase.sample(SimpleNamespace(env=fixture))
    user=new_test_user(shipment.env,login='qa-t81-live-operator',groups='sales_team.group_sale_salesman',company_id=shipment.company_id.id,company_ids=[(6,0,shipment.company_id.ids)])
    order.user_id=user
    record=shipment.with_user(user).with_context(chart_template_load=False)
    assert record.env.ref('step_export.menu_step_export_shipping_instruction').id in record.env['ir.ui.menu']._visible_menu_ids()
    arch=etree.fromstring(record.get_view(view_id=record.env.ref('step_export.view_step_export_export_form').id,view_type='form')['arch'].encode())
    assert all(arch.xpath('.//field[@name="%s"]'%n) for n in ('booking','freight_payment','documentation_ids','freight_ids','quality_id','folio_sale_order_id'))
    assert arch.xpath('.//button[@name="action_complete_instruction_freights"]')
    assert dict(record._fields['freight_payment']._description_selection(record.env))=={'collect':'Collect','prepaid':'Prepaid'}
    assert record.shipment_number==order.export_document_number=='257'
    assert order.with_user(user)._prepare_invoice()['export_folio_sale_order_id']==order.id
    record.documentation_ids[0].write({'originals':5,'status':'sent','date':'2026-11-13'})
    record.action_validate_shipment(); assert record.state=='validated'
    reports=record.env['ir.actions.report']
    html,_=reports._render_qweb_html('step_export_shipping_design.instruction',record.ids)
    assert all(s in html.decode() for s in ('QA BOOKING 81','QA Brand','QA Shipping Quality','FLETES Y DOCUMENTACIÓN','257'))
    tree=etree.HTML(html)
    assert len(tree.xpath('//div[@data-section="documentation"]//tbody/tr'))==5
    assert not tree.xpath('//div[@data-section="documentation"]//th[text()="Estado"]')
    assert len(tree.xpath('//div[@data-section="freights"]//tbody/tr'))==14
    assert tree.xpath('//div[@data-section="product"]//th[text()="CANTIDAD DE CAJAS/SACOS"]')
    assert tree.xpath('//th[@class="critical" and text()="CANTIDAD CONTENEDORES"]')
    original=record.freight_ids.ids
    record.action_complete_instruction_freights()
    assert record.freight_ids.ids==original
    core=record.freight_ids.filtered(lambda f:f.concept_id.name=='THC')
    core.payment='prepaid'
    assert any(row['payment']=='Prepaid' for row in record._instruction_freights())
    # Actual Odoo PDF converter, including paper format and page boundaries.
    pdf,_=reports._render_qweb_pdf('step_export_shipping_design.instruction',record.ids)
    assert pdf.startswith(b'%PDF') and len(pdf)>5000
    Path(OUTPUT,'instruction-preview.pdf').write_bytes(pdf)
    Path(OUTPUT,'instruction-preview.html').write_bytes(html)
    record.notes=''.join('<p>Observación de prueba %02d: coordinación de carga, documentos y entrega.</p>'%i for i in range(18))
    record.line_ids.copy({'shipment_id':record.id,'label':'QA Second Brand'})
    long_pdf,_=reports._render_qweb_pdf('step_export_shipping_design.instruction',record.ids)
    assert long_pdf.startswith(b'%PDF')
    Path(OUTPUT,'instruction-long-preview.pdf').write_bytes(long_pdf)
    print('MANAGEMENT_REGISTRY_OK '+json.dumps({'ticket':83,'versions':EXPECTED,'menus':True,'forms':True,
        'shared_folio':True,'invoice_source':True,'documentation':True,'freights':True,'native_pdf':True,'validation_flow':True,
        'fixed_documentation':True,'fixed_freights':True,'payment_labels':True,'product_layout':True,'critical_fields':True,'legacy_data_preserved':True}))
finally:
    env.cr.rollback()
