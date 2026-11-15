"""Verify the effective T219 menu, installed sources and native form paths."""
import importlib
from pathlib import Path
from xml.etree import ElementTree

module = 'step_harvest_container_control'
parent = env.ref('step_packing_operations.menu_packing_reception_containers')
for name, version in EXPECTED.items():
    row = env['ir.module.module'].search([('name', '=', name), ('state', '=', 'installed')])
    assert row.latest_version == version, (name, row.latest_version, version)
    assert Path(importlib.import_module('odoo.addons.' + name).__file__).resolve().parent == Path(ROOT) / name

users = env['res.users'].search([('share', '=', False), ('active', '=', True)])
stock_user = next(user for user in users if user.has_group('stock.group_stock_user'))
scoped = env(user=stock_user, su=False, context=dict(env.context, allowed_company_ids=stock_user.company_id.ids))
visible = scoped['ir.ui.menu']._visible_menu_ids()
checks = [
    ('step_packing_operations.menu_packing_reception_containers_transfers', 'step.harvest.container.transfer', 'form',
     ['fruit_picking_id', 'dispatch_guide_id', 'lot_id', 'conservation', 'operating']),
    ('step_packing_operations.menu_packing_reception_containers_balance', 'stock.quant', 'list',
     ['lot_id', 'step_container_partner_id', 'step_container_conservation', 'step_container_operating']),
    ('step_packing_operations.menu_packing_reception_containers_ledger', 'stock.move.line', 'list',
     ['lot_id', 'step_container_source_partner_id', 'step_container_dest_partner_id', 'step_container_operating']),
    (module + '.menu_container_inventory', 'stock.quant', 'list',
     ['lot_id', 'step_container_conservation', 'step_container_operating', 'available_quantity']),
    (module + '.menu_container_work_order', 'step.harvest.container.work.order', 'form',
     ['operation', 'lot_id', 'season_account_id', 'center_account_id', 'activity_account_id', 'unit_cost']),
]
for xmlid, model, kind, expected_fields in checks:
    menu = scoped.ref(xmlid)
    assert menu.parent_id == parent and menu.id in visible, xmlid
    action = menu.action
    assert action.res_model == model, xmlid
    view = action.view_id.id if action.view_id.type == kind else None
    arch = ElementTree.fromstring(scoped[model].get_view(view_id=view, view_type=kind)['arch'])
    actual = {node.get('name') for node in arch.findall('.//field')}
    assert set(expected_fields) <= actual, (xmlid, set(expected_fields) - actual)
    if kind == 'list':
        from odoo.tools.safe_eval import safe_eval
        scoped[model].search(safe_eval(action.domain), limit=1)

for model, xmlid, name in [
    ('product.template', 'product.product_template_only_form_view', 'step_harvest_packaging_id'),
    ('step.dispatch.guide', 'step_dispatch_guide.view_dispatch_guide_form', 'step_container_transfer_ids'),
    ('stock.picking', 'stock.view_picking_form', 'step_container_work_order_id'),
    ('step.hrs.machinery', 'step_machinery.view_step_hrs_machinery_form', 'step_container_work_order_id'),
    ('step.tarja', 'step_labor_operations_core.view_step_tarja_form', 'step_container_work_order_id'),
    ('account.move', 'account.view_move_form', 'step_container_work_order_id'),
]:
    arch = env[model].get_view(view_id=env.ref(xmlid).id, view_type='form')['arch']
    assert name in arch, (model, name)
print('MANAGEMENT_REGISTRY_OK ' + env.cr.dbname)
