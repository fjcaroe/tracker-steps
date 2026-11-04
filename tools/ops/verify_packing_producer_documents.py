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
    if 'step_packing_bom_scope' in EXPECTED:
        users = env['res.users'].search([('active', '=', True), ('share', '=', False),
                                        ('id', '!=', 1), ('company_ids', 'in', scoped.company.ids)])
        editors = users.filtered(lambda user: user.has_group('base.group_multi_company')
                                and scoped(user=user, su=False)['mrp.bom'].has_access('write'))
        assert editors, 'An existing multi-company BOM editor is required'
        editor = scoped(user=editors[:1], su=False)
        bom_menu = editor.ref('step_packing_packaging_master.menu_packing_fruit_bom')
        assert bom_menu.id in editor['ir.ui.menu']._visible_menu_ids()
        # The web action loader reads action metadata with elevated access.
        # Resolve the view ID the same way, then render it as the BOM editor.
        view_id = next(view_id for view_id, mode in bom_menu.sudo().action.views if mode == 'form')
        form = etree.fromstring(editor['mrp.bom'].get_view(view_id=view_id, view_type='form')['arch'])
        assert form.xpath("//group/field[@name='company_id']")
        assert form.xpath("//group/field[@name='step_applicable_company_ids']")
    assert 'step_applicable_company_ids' in repr(scoped['ir.rule']._compute_domain('mrp.bom'))
    order = order_model.search([('line_ids', '!=', False)], limit=1) or order_model.search([], limit=1)
    assert order
    assert order._document_xlsx().startswith(b'PK')
    reports = [(scoped.ref(prefix + 'action_order_pdf'), order, 'op')]
    if env.cr.dbname.startswith('MANAGEMENT_QA_'):
        for kind in ('reception', 'process'):
            if kind == 'reception':
                source = env['stock.picking'].search([
                    ('picking_type_code', '=', 'incoming'), ('state', '=', 'done'),
                    ('step_fruit_reception_kind', 'in', ['process', 'packed']),
                    ('fruit_fundo_id.partner_id', '!=', False), ('fruit_tag_line_ids', '!=', False),
                ], order='id desc', limit=1)
                partner = source.fruit_fundo_id.partner_id
            else:
                candidates = env['step.packing.production'].search([
                    ('state', 'in', ['validated', 'closed', 'costed', 'accounted']),
                    ('fruit_grower_id', '!=', False), ('step_packing_input_tag_ids', '!=', False),
                ], order='step_packing_input_kg desc', limit=30)
                source = candidates.filtered(lambda ot: not (
                    (ot.step_packing_input_tag_ids | ot.step_packing_output_tag_ids).step_tag_line_ids.producer_id
                    - ot.fruit_grower_id))[:1]
                partner = source.fruit_grower_id
            operator = scoped_business_environment(env, company=source.company_id if source else None)
            wizard_model = operator['step.packing.producer.document']
            if source and kind == 'reception':
                day = wizard_model._receipt_day(source.with_env(operator))
            else:
                day = source.date if source else order.week_start
            partner = partner or scoped['res.partner'].search([('is_company', '=', True)], limit=1)
            assert partner and day
            wizard = wizard_model.create({
                'kind': kind, 'producer_id': partner.id, 'date_from': day, 'date_to': day,
            })
            if source:
                assert wizard._document_data()['sections'][0][2], f'No data for the selected {kind} record'
            reports.append((operator.ref(prefix + 'action_producer_pdf'), wizard, kind))
        for report, record, key in reports:
            pdf, extension = record.env['ir.actions.report']._render_qweb_pdf(report.report_name, record.ids)
            assert extension == 'pdf' and pdf.startswith(b'%PDF') and len(pdf) > 5000
            (Path(OUTPUT) / 'data' / f'{key}.pdf').write_bytes(pdf)
            (Path(OUTPUT) / 'data' / f'{key}.xlsx').write_bytes(record._document_xlsx())
    print('MANAGEMENT_REGISTRY_OK ' + json.dumps({'tickets': [157, 158, 159, 160], 'versions': EXPECTED}))
finally:
    env.cr.rollback()
