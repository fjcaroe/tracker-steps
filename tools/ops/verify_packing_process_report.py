"""Read-only T156 verification against a Packing OT visible to the business profile."""
import importlib
import io
import json
from pathlib import Path
from zipfile import ZipFile

from lxml import etree, html

from native_business_profile import scoped_business_environment


try:
    for name, version in EXPECTED.items():
        module = env['ir.module.module'].search([('name', '=', name)])
        assert module.state == 'installed' and module.latest_version == version
        assert Path(importlib.import_module('odoo.addons.' + name).__file__).resolve().parent == Path(ROOT) / name
    scoped = scoped_business_environment(env)
    model = scoped['step.packing.production']
    menu = scoped.ref('step_packing_operations.menu_packing_production')
    assert menu.id in scoped['ir.ui.menu']._visible_menu_ids()
    form = scoped.ref('step_packing_operations.view_packing_production_form')
    arch = etree.fromstring(model.get_view(view_id=form.id, view_type='form')['arch'])
    assert arch.xpath("//header/button[@name='action_packing_process_xlsx']")
    action = scoped.ref('step_packing_operations.action_report_packing_process')
    assert action.report_type == 'qweb-pdf' and action.binding_model_id.model == model._name
    domain = [('step_packing_input_tag_ids', '!=', False), ('step_packing_output_tag_ids', '!=', False)]
    record = model.search(domain, order='step_packing_input_kg desc, id desc', limit=1) or model.search([], limit=1)
    assert record
    assert record.action_packing_process_xlsx()['url'] == f'/packing/process/{record.id}/xlsx'
    data = record._packing_report_data()
    assert data['summary'][1][2][0][3] == record.step_packing_overweight_kg
    for (_, _, rows, total) in data['detail']:
        assert total[-2] == sum(row[-2] for row in rows)
        assert total[-1] == sum(row[-1] for row in rows)
    xlsx = record._packing_process_xlsx()
    with ZipFile(io.BytesIO(xlsx)) as book:
        workbook = etree.fromstring(book.read('xl/workbook.xml'))
        assert workbook.xpath("//*[local-name()='sheet']/@name") == ['OT packing', 'OT Anexo']
        sheet = etree.fromstring(book.read('xl/worksheets/sheet1.xml'))
        assert not sheet.xpath("//*[local-name()='f']")
        assert sheet.xpath("//*[local-name()='c'][@s and not(@t)]/*[local-name()='v']")
    content, _ = scoped['ir.actions.report']._render_qweb_html(action.report_name, record.ids)
    rendered = html.fromstring(content)
    assert len(rendered.xpath("//h2[starts-with(normalize-space(.),'INFORME DE PROCESO PACKING')]")) == 2
    assert len(rendered.xpath('//h4')) >= 6
    if env.cr.dbname.startswith('MANAGEMENT_QA_'):
        pdf, _ = scoped['ir.actions.report']._render_qweb_pdf(action.report_name, record.ids)
        assert pdf.startswith(b'%PDF') and len(pdf) > 5000
        (Path(OUTPUT) / 'data' / 'packing.pdf').write_bytes(pdf)
        (Path(OUTPUT) / 'data' / 'packing.xlsx').write_bytes(xlsx)
    print('MANAGEMENT_REGISTRY_OK ' + json.dumps({
        'ticket': 156, 'versions': EXPECTED, 'pdf_and_xlsx': True,
        'input_rows': len(data['detail'][0][2]), 'output_rows': sum(len(s[2]) for s in data['detail'][1:]),
    }))
finally:
    env.cr.rollback()
