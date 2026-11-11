import importlib
import json
from pathlib import Path

from lxml import etree

from native_business_profile import scoped_business_environment


try:
    name = 'step_packing_ticket_revision'
    version = EXPECTED[name]
    module = env['ir.module.module'].search([('name', '=', name), ('state', '=', 'installed')])
    assert module.latest_version == version
    assert Path(importlib.import_module('odoo.addons.' + name).__file__).resolve().parent == Path(ROOT) / name
    scoped = scoped_business_environment(env)
    installed_version = tuple(map(int, version.split('.')))
    menu = scoped.ref('step_packing_ticket_revision.menu_external_fruit_reception_import')
    assert menu.id in scoped['ir.ui.menu']._visible_menu_ids()
    wizard = scoped[menu.action.res_model]
    assert wizard.check_access_rights('create', raise_exception=False)
    arch = etree.fromstring(wizard.get_view(view_id=menu.action.view_id.id, view_type='form')['arch'])
    assert arch.xpath("//button[@name='action_import']") and arch.xpath("//field[@name='file']")
    reception = scoped.ref('step_inventory_packing.action_steps_fruit_process_reception')
    views = dict((kind, ref) for ref, kind in reception.views)
    if installed_version >= (18, 0, 1, 2, 0):
        assert arch.xpath("//field[@name='template_id']") and arch.xpath("//button[@name='action_review']")
        list_view = etree.fromstring(scoped['stock.picking'].get_view(view_id=views['list'], view_type='list')['arch'])
        assert list_view.get('import') == '0'
        assert list_view.xpath("//header/button[@name='%s']" % menu.action.id)
    if installed_version >= (18, 0, 1, 2, 1):
        list_menu = scoped.ref('step_inventory_packing.menu_steps_fruit_process_reception')
        assert list_menu.action == reception and list_menu.id in scoped['ir.ui.menu']._visible_menu_ids()
        columns = ('step_reception_product_ids', 'step_reception_packaging_ids', 'step_reception_container_qty',
                   'step_reception_net_kg', 'step_reception_avg_kg')
        for name in columns:
            field, = list_view.xpath("/list/field[@name=$name]", name=name)
            assert field.get('optional') == 'show'
            if name in ('step_reception_container_qty', 'step_reception_net_kg'):
                assert field.get('sum')
        pickings = scoped['stock.picking'].search([
            ('step_fruit_reception_kind', '=', 'process'), ('state', '=', 'done'),
            ('fruit_tag_line_ids', '!=', False),
        ], limit=12)
        for picking in pickings:
            lines = picking.fruit_tag_line_ids
            containers, kilos = sum(lines.mapped('quantity')), sum(lines.mapped('kilos'))
            if containers and kilos:
                assert abs(picking.step_reception_container_qty - containers) < 1e-7
                assert abs(picking.step_reception_net_kg - kilos) < 1e-7
                assert abs(picking.step_reception_avg_kg - kilos / containers) < 1e-7
        print('MANAGEMENT_REGISTRY_OK ' + json.dumps({'ticket': 197, 'version': version,
              'process_reception_menu': True, 'list_columns_and_sums': True, 'existing_receipts_read': len(pickings)}))
    view = views['form']
    arch = etree.fromstring(scoped['stock.picking'].get_view(view_id=view, view_type='form')['arch'])
    assert arch.xpath("//field[@name='step_external_reception_folio']")
    assert arch.xpath("//field[@name='fruit_tag_line_ids']/list/field[@name='step_fruit_palletized']")
    if installed_version >= (18, 0, 1, 2, 0):
        process_menu = scoped.ref('step_packing_ticket_revision.menu_external_packing_process_import')
        assert process_menu.id in scoped['ir.ui.menu']._visible_menu_ids()
        process = scoped[process_menu.action.res_model]
        arch = etree.fromstring(process.get_view(view_id=process_menu.action.view_id.id, view_type='form')['arch'])
        assert arch.xpath("//field[@name='mapping_ids']") and arch.xpath("//button[@name='action_import']")
        ot = scoped['step.packing.production']
        ot_view = scoped.ref('step_packing_operations.view_packing_production_form')
        assert 'step_external_process_folio' in ot.get_view(view_id=ot_view.id, view_type='form')['arch']
        print('MANAGEMENT_REGISTRY_OK ' + json.dumps({'ticket': 193, 'version': version,
              'process_menu': True, 'reception_templates': True, 'operator': scoped.uid}))
    print('MANAGEMENT_REGISTRY_OK ' + json.dumps({'ticket': 189, 'version': version, 'menu': True, 'wizard': True,
          'native_reception': True, 'business_profile': scoped.uid}))
finally:
    env.cr.rollback()
