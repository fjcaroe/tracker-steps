"""Read-only effective fruit reception source/form probe in Odoo shell."""
import importlib
import json

try:
    name = 'step_inventory_packing'
    assert env['ir.module.module'].search([('name', '=', name)]).latest_version == EXPECTED[name]
    assert importlib.import_module('odoo.addons.' + name).__file__.startswith(ROOT + '/')
    arch = env['stock.picking'].get_view(view_type='form')['arch']
    assert 'fruit_tag_line_ids' in arch and 'action_prepare_fruit_stock' in arch
    print('MANAGEMENT_REGISTRY_OK ' + json.dumps({'versions': EXPECTED, 'fruit_reception_form': True}))
finally:
    env.cr.rollback()
