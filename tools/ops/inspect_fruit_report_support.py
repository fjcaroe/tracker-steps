"""Inspect report/menu prerequisites without reading private receipt data."""
import json
for xmlid in ('stock.menu_warehouse_report','step_hr.action_step_especie','step_management_costs.action_caliber_group','step_management_costs.action_fruit_caliber','step_management_costs.action_fruit_category','step_inventory_fruit_tag.action_fruit_quality','step_export_client_revision.color_action'):
    record=env.ref(xmlid,raise_if_not_found=False)
    assert record,xmlid
    print('XMLID',xmlid,record._name,record.id,record.groups_id.ids if record._name=='ir.ui.menu' else record.res_model)
print('MODULES',json.dumps(env['ir.module.module'].search_read([('name','in',['step_producer_fruit_flow','step_export_client_revision','step_agriculture_catalogs'])],['name','state','latest_version'])))
print('SPECIES_FIELDS',sorted(name for name in env['step.especie']._fields if 'sag' in name or 'pallet' in name))
