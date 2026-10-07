"""Inspect effective Packing forms, menus and user permissions in Odoo shell."""
import importlib
import json
from verify_packing_flow import verify_flow
from lxml import etree
from odoo.tests.common import new_test_user

try:
    for name, version in EXPECTED.items():
        assert env['ir.module.module'].search([('name', '=', name)]).latest_version == version, name
        assert importlib.import_module('odoo.addons.' + name).__file__.startswith(ROOT + '/'), name
    operator = new_test_user(env, login='t41-revision-probe', groups='stock.group_stock_user')
    checked = []
    for model, view in [('step.packing.production', 'view_packing_production_form'),
                        ('step.packing.repack', 'view_packing_repack_form'),
                        ('step.export.stock.reservation', 'view_stock_reservation_packing')]:
        tree = etree.fromstring(env[model].with_user(operator).get_view(
            view_id=env.ref('step_packing_operations.' + view).id, view_type='form')['arch'].encode())
        if model == 'step.packing.production':
            assert tree.xpath('//notebook[1]/page[1]')[0].get('name') == 'outputs'
            assert not tree.xpath("//sheet/group/group/field[@name='product_id']")
            assert tree.xpath("//button[@name='action_create_export_tag']")
            assert tree.xpath("//field[@name='raw_product_id']")
        if model == 'step.export.stock.reservation':
            assert tree.xpath("//field[@name='destination_country_id']")
            assert tree.xpath("//field[@name='sales_program_id']")
            assert tree.xpath("//field[@name='step_package_ids']/list")
        if model == 'step.packing.repack':
            assert tree.xpath("//field[@name='source_tag_ids']") and tree.xpath("//field[@name='target_tag_ids']")
        checked.append(model)
    root = env.ref('step_packing_operations.menu_packing_operations_root')
    for menu in env['ir.ui.menu'].search([('id', 'child_of', root.id)]):
        action = menu.action
        if action and action._name == 'ir.actions.act_window':
            for mode in action.view_mode.split(','):
                if mode in ('list', 'form', 'kanban'):
                    env[action.res_model].get_view(view_type=mode)
    flow = verify_flow(env, operator)
    menu_id = root.id
    env.cr.rollback()
    print('MANAGEMENT_REGISTRY_OK ' + json.dumps({'forms': checked, 'operator': 'Inventory User', 'root_menu': menu_id, 'flow': flow, 'sample_records': 'rolled back'}))
except Exception:
    env.cr.rollback()
    raise
