"""T161 native form and material preparation in the destination clone."""
import importlib
import json
from pathlib import Path

from lxml import etree
from odoo.exceptions import UserError

from native_business_profile import scoped_business_environment


try:
    for name, version in EXPECTED.items():
        module = env['ir.module.module'].search([('name', '=', name)])
        assert module.state == 'installed' and module.latest_version == version
        assert Path(importlib.import_module('odoo.addons.' + name).__file__).resolve().parent == Path(ROOT) / name
    sample = env['step.packing.production'].search([('name', '=', 'OT/2026/00019')])
    assert len(sample) <= 1
    scoped = scoped_business_environment(env, company=sample.company_id if sample else None)
    model = scoped['step.packing.production']
    menu = scoped.ref('step_packing_operations.menu_packing_production')
    assert menu.id in scoped['ir.ui.menu']._visible_menu_ids()
    view = scoped.ref('step_packing_operations.view_packing_production_form')
    arch = etree.fromstring(model.get_view(view_id=view.id, view_type='form')['arch'])
    assert arch.xpath("//button[@name='action_prepare_materials']")
    summary = {'ticket': 161, 'versions': EXPECTED}
    if sample:
        order = model.browse(sample.id)
        order.check_access('read')
        if env.cr.dbname.startswith('MANAGEMENT_QA_'):
            export = order.step_packing_output_tag_ids.filtered(
                lambda tag: tag.step_tag_kind == 'E' and tag.step_packing_result == 'export')
            assert export
            if order.material_review_state == 'approved':
                order.action_reopen_materials()
            before = order.step_packing_output_tag_ids.step_tag_line_ids.read(['product_id', 'boxes', 'quantity'])
            try:
                order.action_prepare_materials()
            except UserError as error:
                # QA-Cerro training data can use a different finished SKU.
                assert env.cr.dbname.startswith('MANAGEMENT_QA_QA-CERRO_')
                raw = order.raw_product_id | order.step_packing_input_tag_ids.step_tag_line_ids.product_id
                finished = export.step_tag_line_ids.product_id - raw
                missing = finished.filtered(lambda product: not scoped['mrp.bom']._bom_find(
                    product, company_id=order.company_id.id).get(product))
                assert 'Configure una lista de materiales para' in str(error)
                assert any(product.display_name in str(error) for product in missing)
                summary['missing_finished_bom'] = missing.mapped('default_code')
            else:
                assert order.material_line_ids.package_id == export
            assert order.step_packing_output_tag_ids.step_tag_line_ids.read(['product_id', 'boxes', 'quantity']) == before
            summary.update(folio=order.name, export_tags=len(export), material_lines=len(order.material_line_ids))
    print('MANAGEMENT_REGISTRY_OK ' + json.dumps(summary))
finally:
    env.cr.rollback()
