"""T157–T160 read-only destination verification."""
import importlib
import json
from datetime import timedelta
from pathlib import Path

from lxml import etree

from native_business_profile import scoped_business_environment


try:
    for name, version in EXPECTED.items():
        module = env['ir.module.module'].search([('name', '=', name)])
        assert module.state == 'installed' and module.latest_version == version
        assert Path(importlib.import_module('odoo.addons.' + name).__file__).resolve().parent == Path(ROOT) / name
    scoped = scoped_business_environment(env)
    prefix = 'step_packing_producer_documents.'
    for name in ('menu_reception', 'menu_process'):
        assert scoped.ref(prefix + name).id in scoped['ir.ui.menu']._visible_menu_ids()
    order_model = scoped['step.packing.order']
    view = scoped.ref('step_packing_operations.view_packing_order_form')
    arch = etree.fromstring(order_model.get_view(view_id=view.id, view_type='form')['arch'])
    assert arch.xpath("//button[@name='action_document_xlsx']")
    bom_view = scoped.ref('mrp.mrp_bom_form_view')
    assert b'step_applicable_company_ids' in etree.tostring(bom_view._get_combined_arch())
    assert 'step_applicable_company_ids' in scoped.ref('mrp.mrp_bom_rule').domain_force
    order = order_model.search([], limit=1)
    assert order
    assert order._document_xlsx().startswith(b'PK')
    reports = [(scoped.ref(prefix + 'action_order_pdf'), order, 'op')]
    if env.cr.dbname.startswith('MANAGEMENT_QA_'):
        producer = scoped['res.partner'].search([('is_company', '=', True)], limit=1)
        assert producer
        for kind in ('reception', 'process'):
            wizard = scoped['step.packing.producer.document'].create({
                'kind': kind, 'producer_id': producer.id,
                'date_from': order.week_start - timedelta(days=7), 'date_to': order.week_end,
            })
            reports.append((scoped.ref(prefix + 'action_producer_pdf'), wizard, kind))
        for report, record, key in reports:
            pdf, extension = scoped['ir.actions.report']._render_qweb_pdf(report.report_name, record.ids)
            assert extension == 'pdf' and pdf.startswith(b'%PDF') and len(pdf) > 5000
            (Path(OUTPUT) / 'data' / f'{key}.pdf').write_bytes(pdf)
            (Path(OUTPUT) / 'data' / f'{key}.xlsx').write_bytes(record._document_xlsx())
    print('MANAGEMENT_REGISTRY_OK ' + json.dumps({'tickets': [157, 158, 159, 160], 'versions': EXPECTED}))
finally:
    env.cr.rollback()
