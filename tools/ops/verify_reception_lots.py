"""T165 verifies the active reception and OT views with the native business profile."""
import importlib
import json
from pathlib import Path
from lxml import etree
from odoo.tools.safe_eval import safe_eval
from native_business_profile import scoped_business_environment

def verify_reception_conditions(scoped, is_copy):
    selections = {
        'step_fruit_gassed': {'yes', 'no'},
        'step_fruit_chilled': {'yes', 'no'},
        'step_fruit_palletized': {'yes', 'no'},
        'step_fruit_reception_classification': {'psj', 'cg', 'gid'},
    }
    model = scoped['stock.picking']
    fields = model.fields_get(list(selections), attributes=['selection', 'required'])
    for name, options in selections.items():
        assert {key for key, _label in fields[name]['selection']} == options
        assert not fields[name]['required']
    result = {}
    for kind in ('process', 'packed'):
        menu = scoped.ref('step_inventory_packing.menu_steps_fruit_' + kind + '_reception')
        assert menu.id in scoped['ir.ui.menu']._visible_menu_ids()
        action = menu.action._get_action_dict()
        view_id = dict((view_type, view) for view, view_type in action['views'])['form']
        form = etree.fromstring(model.get_view(view_id=view_id, view_type='form')['arch'])
        for name in selections:
            node, = form.xpath("//page[@name='step_packing_fruit']//field[@name=$name]", name=name)
            invisible = node.get('invisible')
            readonly = node.get('readonly')
            assert not safe_eval(invisible, {'picking_type_code': 'incoming', 'step_fruit_reception_kind': kind})
            assert safe_eval(invisible, {'picking_type_code': 'outgoing', 'step_fruit_reception_kind': False})
            assert not safe_eval(readonly, {'state': 'draft'}) and safe_eval(readonly, {'state': 'done'})
        if is_copy:
            scoped.company.sudo().step_fruit_inventory_enabled = True
            wh = scoped['stock.warehouse'].search([('company_id', '=', scoped.company.id)], limit=1)
            assert wh and wh.in_type_id.default_location_src_id and wh.lot_stock_id
            entry = model.with_context(**safe_eval(action['context']))
            values = {
                'picking_type_id': wh.in_type_id.id,
                'location_id': wh.in_type_id.default_location_src_id.id,
                'location_dest_id': wh.lot_stock_id.id,
            }
            row = entry.create(values)
            assert row.step_fruit_reception_kind == kind
            assert not any(row[name] for name in selections)
            choices = dict(zip(selections, ('yes', 'no', 'yes', 'cg' if kind == 'process' else 'gid')))
            row.web_save(choices, {name: {} for name in selections})
            row.invalidate_recordset(list(selections))
            assert all(row[name] == choice for name, choice in choices.items())
        result[kind] = {'menu': True, 'form': True, 'saved_in_copy': is_copy}
    return result


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
    version = tuple(map(int, EXPECTED['step_packing_reception_revision'].split('.')))
    if version >= (18, 0, 1, 3, 6):
        result = verify_reception_conditions(scoped, env.cr.dbname.startswith('MANAGEMENT_QA_'))
        print('MANAGEMENT_REGISTRY_OK ' + json.dumps({'ticket': 188, 'receptions': result}))
    if version >= (18, 0, 1, 3, 7):
        action = scoped.ref('step_inventory_packing.menu_steps_fruit_process_reception').action
        form_id = dict((kind, view) for view, kind in action.views)['form']
        arch = etree.fromstring(picking.get_view(view_id=form_id, view_type='form')['arch'])
        assert arch.xpath("//button[@name='action_step_correct_c_product']")
        assert arch.xpath("//button[@name='action_step_view_product_corrections']")
        wizard = scoped['step.reception.product.correction'].get_view(view_type='form')['arch']
        assert all(name in wizard for name in ('line_ids', 'product_id', 'reason', 'action_apply'))
        print('MANAGEMENT_REGISTRY_OK ' + json.dumps({'ticket': 196, 'native_form_and_wizard': True}))
finally:
    env.cr.rollback()
