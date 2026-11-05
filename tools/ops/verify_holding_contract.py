"""T170 effective native monthly form and permitted holding contract selection."""
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
    menu = scoped.ref('step_packing_operations.menu_packing_monthly_fruit_bill', raise_if_not_found=False)
    action = scoped.ref('step_packing_operations.action_monthly_fruit_bill')
    menus = scoped['ir.ui.menu'].search([('action', '=', 'ir.actions.act_window,%s' % action.id)])
    assert set(menus.ids) & scoped['ir.ui.menu']._visible_menu_ids()
    arch = etree.fromstring(scoped['step.packing.monthly.fruit.bill'].get_view(
        view_id=scoped.ref('step_packing_operations.view_monthly_fruit_bill').id, view_type='form')['arch'])
    assert arch.xpath("//field[@name='contract_id']")
    sample = env['step.packing.production'].search([('name', '=', 'OT/2026/00019')], limit=1)
    if sample:
        companies = sample.company_id.sudo().search([('id', 'parent_of', sample.company_id.id)])
        row = sample.with_context(allowed_company_ids=companies.ids)
        assert sample.company_id in row._contract_companies()
    print('MANAGEMENT_REGISTRY_OK ' + json.dumps({
        'ticket': 170, 'versions': EXPECTED, 'existing_profile': scoped.uid,
        'native_monthly_form': True, 'writes': False}))
finally:
    env.cr.rollback()
