import importlib
import json
from pathlib import Path

from lxml import etree
from odoo.tools.float_utils import float_compare

from native_business_profile import scoped_business_environment


try:
    if 'step_packing_interplant' in EXPECTED:
        exec(compile((Path(PROBE_TOOLS) / 'verify_interplant_dispatch.py').read_text(), 'verify_interplant_dispatch.py', 'exec'))
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
        precision = scoped['decimal.precision'].precision_get('Stock Weight')
        container_precision = scoped['decimal.precision'].precision_get('Product Unit of Measure')
        for picking in pickings:
            lines = picking.fruit_tag_line_ids
            containers, kilos = sum(lines.mapped('quantity')), sum(lines.mapped('kilos'))
            if containers and kilos:
                assert float_compare(picking.step_reception_container_qty, containers,
                                     precision_digits=container_precision) == 0
                assert float_compare(picking.step_reception_net_kg, kilos, precision_digits=precision) == 0
                assert float_compare(picking.step_reception_avg_kg, kilos / containers,
                                     precision_digits=precision) == 0
        print('MANAGEMENT_REGISTRY_OK ' + json.dumps({'ticket': 197, 'version': version,
              'process_reception_menu': True, 'list_columns_and_sums': True, 'existing_receipts_read': len(pickings)}))
    view = views['form']
    arch = etree.fromstring(scoped['stock.picking'].get_view(view_id=view, view_type='form')['arch'])
    assert arch.xpath("//field[@name='step_external_reception_folio']")
    assert arch.xpath("//field[@name='fruit_tag_line_ids']/list/field[@name='step_fruit_palletized']")
    if 'step_packing_reception_revision' in EXPECTED and installed_version >= (18, 0, 1, 2, 4):
        assert arch.xpath("//button[@name='action_step_reverse_fruit_receipt']")
        assert arch.xpath("//field[@name='step_fruit_correction_of_id']")
        folio_index = ('step_external_active_reception_folio_farm' if installed_version >= (18, 0, 1, 2, 6)
                       else 'step_external_active_reception_folio')
        env.cr.execute("SELECT to_regclass(%s)", [folio_index])
        assert env.cr.fetchone()[0]
        dispatch_menu = scoped.ref('step_dispatch_guide.menu_dispatch_types')
        assert dispatch_menu.id in scoped['ir.ui.menu']._visible_menu_ids()
        types = scoped[dispatch_menu.action.res_model]
        dispatch_arch = etree.fromstring(types.get_view(view_type='form')['arch'])
        assert dispatch_arch.xpath("//field[@name='company_ids']")
        guide = scoped.ref('step_dispatch_guide.view_dispatch_guide_form')
        guide_arch = etree.fromstring(scoped[guide.model].get_view(view_id=guide.id, view_type='form')['arch'])
        assert guide_arch.xpath("//field[@name='dispatch_type_id' and contains(@domain, 'company_ids')]")
        print('MANAGEMENT_REGISTRY_OK ' + json.dumps({'tickets': [204, 205, 206],
              'dispatch_types': True, 'active_folio': True, 'reversal': True}))
    if installed_version >= (18, 0, 1, 2, 6):
        assert 'cada combinación de referencia y fundo' in wizard.with_context(lang='es_CL').get_view(
            view_id=menu.action.view_id.id, view_type='form')['arch']
        env.cr.execute("SELECT to_regclass('step_external_active_reception_folio_farm'), "
                       "to_regclass('step_external_active_reception_folio')")
        current_index, previous_index = env.cr.fetchone()
        assert current_index and not previous_index
        print('T214_REGISTRY_OK ' + json.dumps({'import_menu': True, 'wizard': True, 'unique_per_farm': True}))
    if installed_version >= (18, 0, 1, 2, 0):
        process_menu = scoped.ref('step_packing_ticket_revision.menu_external_packing_process_import')
        assert process_menu.id in scoped['ir.ui.menu']._visible_menu_ids()
        process = scoped[process_menu.action.res_model]
        arch = etree.fromstring(process.get_view(view_id=process_menu.action.view_id.id, view_type='form')['arch'])
        assert arch.xpath("//field[@name='mapping_ids']") and arch.xpath("//button[@name='action_import']")
        ot = scoped['step.packing.production']
        ot_view = scoped.ref('step_packing_operations.view_packing_production_form')
        ot_arch = etree.fromstring(ot.get_view(view_id=ot_view.id, view_type='form')['arch'])
        assert ot_arch.xpath("//field[@name='step_external_process_folio']")
        if installed_version >= (18, 0, 1, 2, 2):
            assert arch.xpath("//field[@name='commercial_product_id']")
            assert ot_arch.xpath("//field[@name='step_packing_overweight_kg']")
        if installed_version >= (18, 0, 1, 2, 3):
            assert arch.xpath("//field[@name='pallet_type_id']")
            assert ot_arch.xpath("//page[@name='external_partial_inputs']/field[@name='step_external_input_ids']")
            package = scoped.ref('step_inventory_packing.view_quant_package_form_steps_fruit')
            package_arch = etree.fromstring(scoped[package.model].get_view(view_id=package.id, view_type='form')['arch'])
            assert package_arch.xpath("//field[@name='step_external_completion_source_ids']")
            assert package_arch.xpath("//field[@name='step_external_source_variety_id']")
        print('MANAGEMENT_REGISTRY_OK ' + json.dumps({'ticket': 193, 'version': version,
              'process_menu': True, 'reception_templates': True, 'operator': scoped.uid}))
    print('MANAGEMENT_REGISTRY_OK ' + json.dumps({'ticket': 189, 'version': version, 'menu': True, 'wizard': True,
          'native_reception': True, 'business_profile': scoped.uid}))
    if 'step_application_profiles' in EXPECTED:
        name = 'step_application_profiles'
        profiles = env['ir.module.module'].search([('name', '=', name), ('state', '=', 'installed')])
        assert profiles.latest_version == EXPECTED[name]
        assert Path(importlib.import_module('odoo.addons.' + name).__file__).resolve().parent == Path(ROOT) / name
        users = scoped.ref('base.view_users_form')
        users_arch = etree.fromstring(scoped['res.users'].get_view(view_id=users.id, view_type='form')['arch'])
        assert users_arch.xpath("//page[@name='step_master_access']//field[@name='step_farm_master_access']")
        root = scoped.ref('step_application_profiles.menu_step_user_masters')
        farm_menu = scoped.ref('step_application_profiles.menu_step_user_farms')
        assert farm_menu.parent_id == root and farm_menu.action.res_model == 'step.fundo'
        assert root.id not in scoped['ir.ui.menu']._visible_menu_ids()
        print('MANAGEMENT_REGISTRY_OK ' + json.dumps({'ticket': 203, 'version': profiles.latest_version,
              'user_profile_form': True, 'native_farm_action': True, 'opt_in': True}))
finally:
    env.cr.rollback()
