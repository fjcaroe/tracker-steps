"""Compare every visible package and packing order in the original list requests by user and company."""
import hashlib
import json

from odoo.exceptions import AccessError


FIELDS = {
    'step.packing.production': ['name','state','company_id','date','fruit_grower_id','fruit_variety_id','raw_product_id',
        'step_packing_order_id','step_packing_input_kg','step_packing_export_kg','step_packing_commercial_kg',
        'step_packing_precaliber_kg','step_packing_waste_kg','step_packing_loss_kg','step_packing_export_percent',
        'effective_hours','kg_hour','kg_worker_hour','material_review_state'],
    'stock.quant.package': ['name','company_id','location_id','step_tag_state','harvest_date','received_at','step_tag_kind',
        'package_type_id','especie_id','variedad_id','fruit_category_id','fruit_type','step_producer_id',
        'step_packaging_id','step_actual_kg','step_packing_date','step_packing_partner_id','fundo_id','box_count'],
}


def capture(env):
    probes={}
    users=env['res.users'].search([('active','=',True),('share','=',False),('id','!=',1)],order='id')
    for uid in users:
        companies=sorted(uid.company_ids.ids)
        for scope in [companies,*([cid] for cid in companies if len(companies)>1)]:
            key=str(uid.id)+'/'+','.join(map(str,scope))
            probes[key]={}
            for model,names in FIELDS.items():
                obj=env[model].with_user(uid).with_context(allowed_company_ids=scope,lang='en_US')
                try:
                    with env.cr.savepoint():
                        rows=obj.search_read([],fields=names,order='id')
                        payload=json.dumps(rows,sort_keys=True,default=str).encode()
                        probes[key][model]=dict(count=len(rows),sha256=hashlib.sha256(payload).hexdigest())
                except AccessError:
                    probes[key][model]=dict(denied=True)
    env.cr.rollback()
    return probes
