"""T85/T86 installed origin, effective forms, workflow and native exports; rollback."""
import importlib
import json
from pathlib import Path
from types import SimpleNamespace
from lxml import etree
from odoo.addons.step_export_document_revision.tests.test_documents import DocumentCase

try:
    for name, version in EXPECTED.items():
        module = env['ir.module.module'].search([('name', '=', name)])
        assert module.state == 'installed' and module.latest_version == version
        assert Path(importlib.import_module('odoo.addons.' + name).__file__).resolve().parent == Path(ROOT)/name
    order, packing = DocumentCase.sample(SimpleNamespace(env=env))
    order.step_price_kg = True
    assert order.amount_total == 150 and order.order_line._prepare_invoice_line()['price_unit'] == 15
    assert packing._document_rows()[0][5:8] == [10, 50, 53]
    assert packing.kg_qty == 50
    assert order.order_line.step_document_uom_id == order.order_line.product_id.uom_id
    assert env.ref('step_export.action_export_packing_list').res_model == packing._name
    for model, record in [('sale.order', order), ('step.export.packing.list', packing), ('step.packing.production', packing.tag_ids.step_packing_production_id)]:
        tree = etree.fromstring(record.get_view(view_type='form')['arch'].encode())
        assert tree.tag == 'form'
        if model == 'step.packing.production': assert tree.xpath('.//field[@name="date"]')
    reports = order.env['ir.actions.report']
    for report, record, filename in [('step_sale_export_report.proforma', order, 'proforma'),
        ('step_export_document_revision.commercial_invoice', order, 'invoice'),
        ('step_export.action_report_export_packing_list', packing, 'packing')]:
        pdf, _ = reports._render_qweb_pdf(report, record.ids)
        assert pdf.startswith(b'%PDF') and len(pdf) > 5000
        Path(OUTPUT, filename + '-preview.pdf').write_bytes(pdf)
    Path(OUTPUT, 'packing-preview.xlsx').write_bytes(packing._document_xlsx())
    print('MANAGEMENT_REGISTRY_OK ' + json.dumps({'tickets':[85,86], 'versions': EXPECTED,
        'forms':True, 'pricing':True, 'invoice_values':True, 'net_weight_form':True,
        'unit_from_product':True, 'pdf':True, 'xlsx':True}))
finally:
    env.cr.rollback()
