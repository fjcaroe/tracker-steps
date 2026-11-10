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
    menu = scoped.ref('step_packing_ticket_revision.menu_external_fruit_reception_import')
    assert menu.id in scoped['ir.ui.menu']._visible_menu_ids()
    wizard = scoped[menu.action.res_model]
    assert wizard.check_access_rights('create', raise_exception=False)
    arch = etree.fromstring(wizard.get_view(view_id=menu.action.view_id.id, view_type='form')['arch'])
    assert arch.xpath("//button[@name='action_import']") and arch.xpath("//field[@name='file']")
    reception = scoped.ref('step_inventory_packing.action_steps_fruit_process_reception')
    views = dict((kind, ref) for ref, kind in reception.views)
    if tuple(map(int, version.split('.'))) >= (18, 0, 1, 2, 0):
        assert arch.xpath("//field[@name='template_id']") and arch.xpath("//button[@name='action_review']")
        list_view = etree.fromstring(scoped['stock.picking'].get_view(view_id=views['list'], view_type='list')['arch'])
        assert list_view.get('import') == '0'
        assert list_view.xpath("//header/button[@name='%s']" % menu.action.id)
    view = views['form']
    arch = etree.fromstring(scoped['stock.picking'].get_view(view_id=view, view_type='form')['arch'])
    assert arch.xpath("//field[@name='step_external_reception_folio']")
    assert arch.xpath("//field[@name='fruit_tag_line_ids']/list/field[@name='step_fruit_palletized']")
    print('MANAGEMENT_REGISTRY_OK ' + json.dumps({'ticket': 189, 'version': version, 'menu': True, 'wizard': True,
          'native_reception': True, 'business_profile': scoped.uid}))
finally:
    env.cr.rollback()
