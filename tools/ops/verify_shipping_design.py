"""T81 effective form, shared folio, native print and role workflow; rollback."""
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
    user=new_test_user(shipment.env,login='qa-t81-live-operator',groups='stock.group_stock_user,sales_team.group_sale_salesman',company_id=shipment.company_id.id,company_ids=[(6,0,shipment.company_id.ids)])
    record=shipment.with_user(user).with_context(chart_template_load=False)
    assert record.env.ref('step_export.menu_step_export_shipping_instruction').id in record.env['ir.ui.menu']._visible_menu_ids()
    arch=etree.fromstring(record.get_view(view_id=record.env.ref('step_export.view_step_export_export_form').id,view_type='form')['arch'].encode())
    assert all(arch.xpath('.//field[@name="%s"]'%n) for n in ('booking','freight_payment','documentation_ids','freight_ids','quality_id','folio_sale_order_id'))
    assert record.shipment_number==order.export_document_number=='257'
    assert order._prepare_invoice()['export_folio_sale_order_id']==order.id
    record.documentation_ids[0].write({'originals':5,'status':'sent','date':'2026-11-13'})
    record.action_validate_shipment(); assert record.state=='validated'
    reports=record.env['ir.actions.report']
    html,_=reports._render_qweb_html('step_export_shipping_design.instruction',record.ids)
    assert all(s in html.decode() for s in ('QA BOOKING 81','QA Brand','QA Shipping Quality','FLETES Y DOCUMENTACIÓN','257'))
    # Actual Odoo PDF converter, including paper format and page boundaries.
    pdf,_=reports._render_qweb_pdf('step_export_shipping_design.instruction',record.ids)
    assert pdf.startswith(b'%PDF') and len(pdf)>5000
    Path(OUTPUT,'instruction-preview.pdf').write_bytes(pdf)
    Path(OUTPUT,'instruction-preview.html').write_bytes(html)
    print('MANAGEMENT_REGISTRY_OK '+json.dumps({'ticket':81,'versions':EXPECTED,'menus':True,'forms':True,
        'shared_folio':True,'invoice_source':True,'documentation':True,'freights':True,'native_pdf':True,'validation_flow':True}))
finally:
    env.cr.rollback()
