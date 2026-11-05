"""T165 verifies the active reception and OT views with the native business profile."""
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
    scoped = scoped_business_environment(env)
    picking = scoped['stock.picking']
    view = scoped.ref('step_packing_reception_revision.view_process_reception_form')
    arch = etree.fromstring(picking.get_view(view_id=view.id, view_type='form')['arch'])
    assert arch.xpath("//field[@name='fruit_lot']")
    assert arch.xpath("//field[@name='fruit_tag_line_ids']")
    package_form = scoped['stock.quant.package'].get_view(view_type='form')['arch']
    assert 'lot_id' in package_form
    order = scoped['step.packing.production']
    order_form = order.get_view(view_id=scoped.ref('step_packing_operations.view_packing_production_form').id, view_type='form')['arch']
    assert 'step_packing_input_tag_ids' in order_form
    assert scoped['step.fruit.package.line']._fields['lot_id'].comodel_name == 'stock.lot'
    assert picking.check_access_rights('write', raise_exception=False)
    print('MANAGEMENT_REGISTRY_OK ' + json.dumps({'ticket': 165, 'versions': EXPECTED,
          'native_reception_form': True, 'native_tag_and_order_form': True, 'business_profile': scoped.uid}))
finally:
    env.cr.rollback()
