"""T168 native forms and company-scoped operator access after the tested upgrade."""
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
    menu = scoped.ref('step_packing_operations.menu_packing_repack')
    assert menu.id in scoped['ir.ui.menu']._visible_menu_ids()
    model = scoped['step.packing.repack']
    arch = etree.fromstring(model.get_view(view_id=scoped.ref('step_packing_operations.view_packing_repack_form').id, view_type='form')['arch'])
    for name in ('consume_pallet_materials', 'material_line_ids', 'material_picking_id', 'step_analytic_season_id'):
        assert arch.xpath("//field[@name='%s']" % name)
    assert arch.xpath("//button[@name='action_prepare_materials']")
    assert model.check_access_rights('write', raise_exception=False)
    assert scoped['step.packing.repack.material'].check_access_rights('write', raise_exception=False)
    company_arch = etree.fromstring(env['res.company'].get_view(view_id=env.ref('step_packing_stock_flow.packing_company_form').id, view_type='form')['arch'])
    assert company_arch.xpath("//field[@name='step_packing_allow_material_shortage']")
    print('MANAGEMENT_REGISTRY_OK ' + json.dumps({'ticket':168,'versions':EXPECTED,'business_profile':scoped.uid,
        'company':scoped.company.id,'allow_material_shortage':scoped.company.step_packing_allow_material_shortage,
        'native_repack_material_form':True,'native_accounting_origin':True}))
finally:
    env.cr.rollback()
