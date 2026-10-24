"""Native master tares with the existing destination business profile; no writes."""
import importlib
import json
from pathlib import Path
from lxml import etree
from odoo.tools import config
from native_business_profile import scoped_business_environment

try:
    for name, version in EXPECTED.items():
        module = env['ir.module.module'].search([('name', '=', name)])
        assert module.state == 'installed' and module.latest_version == version
        assert Path(importlib.import_module('odoo.addons.' + name).__file__).resolve().parent == Path(ROOT) / name
    scoped = scoped_business_environment(env)
    previous = config['test_enable']; config['test_enable'] = True
    try:
        from odoo.tests import Form
    finally:
        config['test_enable'] = previous
    checked = []
    for model_name, field, view, action_name in (
        ('product.packaging', 'step_tare_weight', 'view_step_export_packaging_form', 'action_step_export_packaging'),
        ('stock.package.type', 'base_weight', 'view_step_export_package_type_form', 'action_step_export_package_type')):
        model = scoped[model_name]
        action = scoped.ref('step_export.' + action_name)
        menus = scoped['ir.ui.menu'].search([('action', '=', 'ir.actions.act_window,%s' % action.id)])
        packing_root = scoped.ref('step_packing_operations.menu_packing_operations_root')
        packing_menus = menus.filtered(lambda m: str(packing_root.id) in m.parent_path.split('/'))
        assert packing_menus and any(m.id in scoped['ir.ui.menu']._visible_menu_ids() for m in packing_menus)
        assert action.res_model == model_name
        view_ref = 'step_export.' + view
        assert scoped.ref(view_ref).id in action.view_ids.mapped('view_id').ids
        arch = etree.fromstring(model.get_view(view_id=scoped.ref(view_ref).id, view_type='form')['arch'])
        assert len(arch.xpath("//field[@name='%s']" % field)) == 1
        assert model._fields[field].digits == (16, 2)
        assert model.check_access_rights('write', raise_exception=False)
        record = model.search([], limit=1)
        assert record
        record.check_access_rule('write')
        Form(record, view=view_ref)
        checked.append({'model': model_name, 'field': field, 'record': record.id, 'packing_menu': packing_menus.ids})
    print('MANAGEMENT_REGISTRY_OK ' + json.dumps({'ticket':117, 'versions':EXPECTED,
        'existing_profile':scoped.uid, 'company_id':scoped.company.id, 'native_menu_and_form':True,
        'two_decimals':True, 'native_pallet_weight':True, 'masters':checked, 'writes':False}))
finally:
    env.cr.rollback()
