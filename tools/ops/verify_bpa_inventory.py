"""Verify the live foliar application's effective menu and inventory form."""
import importlib
import json
from pathlib import Path

from lxml import etree


try:
    name = 'step_bpa_inventory'
    installed = env['ir.module.module'].search([('name', '=', name)])
    assert installed.state == 'installed' and installed.latest_version == EXPECTED[name]
    source = Path(importlib.import_module('odoo.addons.' + name).__file__).resolve().parent
    assert source == Path(ROOT) / name

    company = env.ref('base.main_company')
    menu = env.ref('step_bpa_irrigation.menu_bpa_applications')
    assert menu.active and menu.action.res_model == 'step.agriculture.application'
    users = env['res.users'].search([
        ('active', '=', True), ('share', '=', False), ('id', '!=', 1),
        ('company_ids', 'in', company.ids),
    ])
    registry = env(context=dict(env.context, allowed_company_ids=company.ids))
    reviewer = next((user for user in users if menu.id in registry['ir.ui.menu'].with_user(user)._visible_menu_ids()), None)
    assert reviewer, 'No existing BPA user can see the foliar application menu'
    apps = registry['step.agriculture.application'].with_user(reviewer)
    assert not apps.env.su
    form_id = env.ref('step_agriculture_records.view_application_form').id
    form = etree.fromstring(apps.get_view(view_id=form_id, view_type='form')['arch'])
    assert form.xpath("//field[@name='consumption_line_ids']/list/field[@name='product_qty']")
    assert form.xpath("//button[@name='action_generate_inventory_move']")
    current = apps.search([('company_id', '=', company.id)], limit=1)
    if current:
        current.web_read({'name': {}, 'state': {}, 'consumption_line_ids': {'fields': {'product_qty': {}}}})
    picking_type = env.ref('step_bpa_inventory.picking_type_bpa_consumption')
    assert picking_type.company_id == company and picking_type.sequence_code == 'BPACONS'
    assert picking_type.default_location_src_id.usage == 'internal'
    assert picking_type.default_location_dest_id.usage == 'production'
    print('MANAGEMENT_REGISTRY_OK ' + json.dumps({
        'ticket': 221, 'versions': EXPECTED, 'menu_and_form': True, 'existing_application_read': bool(current),
    }))
finally:
    env.cr.rollback()
