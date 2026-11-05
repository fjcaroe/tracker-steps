"""T166 native OT and tag views, using an existing business editor."""
import importlib
import json
from pathlib import Path
from lxml import etree
from native_business_profile import scoped_business_environment

try:
    for name, version in EXPECTED.items():
        module = env['ir.module.module'].search([('name', '=', name)])
        assert module.state == 'installed' and module.latest_version == version
        assert Path(importlib.import_module('odoo.addons.' + name).__file__).resolve().parent == Path(ROOT) / name
    sample = env['step.packing.production'].search([('name', '=', 'OT/2026/00019')], limit=1)
    scoped = scoped_business_environment(env, company=sample.company_id if sample else None)
    model = scoped['step.packing.production']
    menu = scoped.ref('step_packing_operations.menu_packing_production')
    assert menu.id in scoped['ir.ui.menu']._visible_menu_ids()
    arch = etree.fromstring(model.get_view(
        view_id=scoped.ref('step_packing_operations.view_packing_production_form').id, view_type='form')['arch'])
    assert arch.xpath("//field[@name='step_output_lot_name']")
    assert model._fields['step_output_lot_name'].string == 'LOTE'
    assert model.check_access_rights('write', raise_exception=False)
    tag_arch = etree.fromstring(scoped['stock.quant.package'].get_view(view_type='form')['arch'])
    assert tag_arch.xpath("//field[@name='lot_id']")
    assert scoped['step.fruit.package.line']._fields['lot_id'].comodel_name == 'stock.lot'
    if sample:
        row = model.browse(sample.id)
        row.read(['name', 'step_output_lot_name'])
        row.step_packing_output_tag_ids.step_tag_line_ids.read(['product_id', 'lot_id'])
    print('MANAGEMENT_REGISTRY_OK ' + json.dumps({'ticket': 166, 'versions': EXPECTED,
          'native_ot_lot_field': True, 'native_tag_lot_field': True, 'business_profile': scoped.uid}))
finally:
    env.cr.rollback()
