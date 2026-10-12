"""Read counts, foreign keys and menu targets for T73-T75 without client values."""
import json
for name in ('step.packing.fruit.class','step.packing.fruit.category','step.management.fruit.category','step.management.fruit.class','step.export.estimate.line','stock.package.type'):
    print('COUNT',name,env[name].with_context(active_test=False).search_count([]))
for model in env.registry.models:
    for name,field in env[model]._fields.items():
        if getattr(field,'comodel_name',None) in ('step.packing.fruit.class','step.packing.fruit.category'):
            print('LEGACY_RELATION',model,name,field.type,field.comodel_name,env[model].sudo().with_context(active_test=False).search_count([(name,'!=',False)]))
for xmlid in ('step_packing_operations.menu_packing_config_fruit_category','step_packing.menu_packing_fruta_fruit_class','step_packing.menu_packing_fruta_fruit_category'):
    r=env.ref(xmlid);print('MENU',xmlid,r.name,r.action.res_model)
for n in ('step_producers','step_export','step_packing_operations','step_producer_estimate_report','step_producer_fruit_reports'):
    r=env['ir.module.module'].search([('name','=',n)]);print('MODULE',n,r.state,r.latest_version)
for name in ('step.packing.fruit.class','step.packing.fruit.category','step.management.fruit.category'):
    print('CATALOG',name,env[name].with_context(active_test=False).search_read([],['name','company_id']))
env.cr.rollback()
