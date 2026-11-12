"""Inspect the destination dropdown with only the dispatch branch active; read-only."""
import json
import os
from native_business_profile import scoped_business_environment
try:
    guide = env['step.dispatch.guide'].search([('name','=',os.environ['INSPECT_GUIDE'])])
    assert len(guide) == 1
    business = scoped_business_environment(env, company=guide.company_id)
    guide = business['step.dispatch.guide'].browse(guide.id)
    company = guide.step_destination_company_id
    domain = [('company_id','=',company.id)]
    print('DESTINATION_SCOPE '+json.dumps({'guide':guide.name,'state':guide.state,
        'source_company':guide.company_id.id,'destination_company':company.id,
        'active_companies':business.companies.ids,'destination_membership':company in business.user.company_ids,
        'warehouses_current':business['stock.warehouse'].search(domain).ids,
        'warehouses_destination':business['stock.warehouse'].with_company(company).search(domain).read(['name','company_id']),
        'selected_warehouse':guide.step_destination_warehouse_id.id,'source_picking':guide.picking_id.id,
        'destination_picking':guide.step_destination_picking_id.id,
        'tags':guide.load_tag_ids.read(['name','step_tag_kind','step_tag_state','box_count','step_actual_kg']),
        'destination_same_folios':business['stock.quant.package'].with_company(company).search([('company_id','=',company.id),('name','in',guide.load_tag_ids.mapped('name'))]).read(['name','step_tag_state','box_count','step_actual_kg']),
        'source_lots':guide.load_tag_ids.quant_ids.lot_id.read(['name','product_id','company_id','step_interplant_origin_lot_id'])}))
finally:
    env.cr.rollback()
