"""T166 native OT and tag views, using an existing business editor."""
import importlib
import json
from pathlib import Path
from lxml import etree
from odoo.tools.safe_eval import safe_eval
from native_business_profile import scoped_business_environment


def verify_caliber_catalog(env, ot_form, *, is_copy):
    sample = env['stock.quant.package'].search([
        ('is_fruit_tag', '=', True), ('fruit_caliber_id.active', '=', True),
    ], limit=1)
    caliber = sample.fruit_caliber_id or env['step.management.fruit.caliber'].search([], limit=1)
    assert caliber, 'The destination must have an existing native fruit caliber'
    business = scoped_business_environment(env, company=caliber.company_id)
    menu = business.ref('step_packing_operations.menu_packing_config_fruit_caliber')
    assert menu.id in business['ir.ui.menu']._visible_menu_ids()
    action = menu.action
    assert action == business.ref('step_management_costs.action_fruit_caliber')
    tags = business['stock.quant.package']
    assert action.res_model == tags._fields['fruit_caliber_id'].comodel_name
    assert ot_form.xpath("//field[@name='step_packing_output_tag_ids']//field[@name='fruit_caliber_id']")
    catalog = business[action.res_model].with_context(**safe_eval(action.context or '{}'))
    view_id = next(ref for ref, kind in action._get_action_dict()['views'] if kind == 'list')
    view = etree.fromstring(catalog.get_view(view_id=view_id, view_type='list')['arch'])
    for name in ('code', 'name', 'group_id', 'step_contract_caliber_id', 'step_2j_plus'):
        assert view.xpath("//field[@name=$name]", name=name), name
    domain = safe_eval(action.domain or '[]') + [('id', '=', caliber.id)]
    result = catalog.web_search_read(domain, {
        'code': {}, 'name': {}, 'step_2j_plus': {},
        'group_id': {'fields': {'display_name': {}}},
        'step_contract_caliber_id': {'fields': {'display_name': {}}},
    }, limit=1)
    assert [row['id'] for row in result['records']] == caliber.ids
    assert [key for key, _label in catalog.name_search(args=[('id', '=', caliber.id)])] == caliber.ids
    if is_copy:
        tag = tags.create({'name': 'QA199 Calibre de fruta', 'company_id': business.company.id,
                           'is_fruit_tag': True, 'step_tag_kind': 'E', 'fruit_caliber_id': caliber.id})
        tag.invalidate_recordset(['fruit_caliber_id'])
        assert tag.fruit_caliber_id == caliber and tag.step_tag_state == 'created' and not tag.quant_ids
    return {'same_catalog_as_tags': True, 'existing_caliber_selectable': True, 'saved_on_copy_tag': is_copy}


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
    if tuple(map(int, EXPECTED['step_packing_operations'].split('.'))) >= (18, 0, 2, 12, 1):
        result = verify_caliber_catalog(env, arch, is_copy=env.cr.dbname.startswith('MANAGEMENT_QA_'))
        print('MANAGEMENT_REGISTRY_OK ' + json.dumps({'ticket': 199, 'fruit_caliber_menu': result}))
finally:
    env.cr.rollback()
