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

def controls(env):
    assert env.cr.dbname in ('MANAGEMENT_QA_CERRO_BOM_20261126U42N','COMMUNITY_CERRO_BOM_PACKING_20261127U46A','COMMUNITY_CERRO_BOM_PACKING_20261127U46C')
    actor=env['res.users'].browse(6)
    allowed={'allowed_company_ids':actor.company_ids.ids,'lang':'en_US'}
    orders=env['step.packing.production'].with_user(actor).with_context(**allowed)
    packages=env['stock.quant.package'].with_env(orders.env)
    order=orders.search([('state','=','created')],limit=1,order='id')
    assert order
    env.cr.execute("SELECT count(*) FROM step_packing_downtime")
    assert env.cr.fetchone()==(0,)
    env.cr.execute("INSERT INTO step_packing_stop_reason(id,company_id,name) VALUES(-921,%s,'U46 QA')",(order.company_id.id,))
    env.cr.execute("""UPDATE step_packing_production SET started_at='2025-05-01 09:00:00',finished_at='2025-05-01 13:00:00',
        workers=2, step_packing_input_kg=180,step_packing_export_kg=90 WHERE id=%s""",(order.id,))
    env.cr.execute("""INSERT INTO step_packing_downtime(id,production_id,company_id,reason_id,started_at,finished_at)
        VALUES(-921,%s,%s,-921,'2025-05-01 10:00:00','2025-05-01 11:00:00')""",(order.id,order.company_id.id))
    metrics=['effective_hours','kg_hour','kg_worker_hour','step_packing_export_percent']
    env.invalidate_all(flush=False)
    performance=[order[name] for name in metrics]
    assert performance==[3,60,30,50],performance
    env.cr.execute("UPDATE step_packing_production SET finished_at=NULL,workers=0,step_packing_input_kg=0 WHERE id=%s",(order.id,))
    env.invalidate_all(flush=False)
    missing=[order[name] for name in metrics]
    assert missing==[0,0,0,0],missing
    line=env['step.fruit.package.line'].with_env(orders.env).search([],limit=1,order='id')
    package=line.package_id
    before=package.step_actual_kg
    env.cr.execute("UPDATE step_fruit_package_line SET kilos=kilos+7 WHERE id=%s",(line.id,))
    env.invalidate_all(flush=False)
    weight_delta=round(package.step_actual_kg-before,6)
    assert weight_delta==7
    known=packages.search([('step_tag_state','not in',('created','void')),('is_fruit_tag','=',True)],limit=1)
    assert known
    from odoo.exceptions import UserError
    try:
        with env.cr.savepoint():
            known.write({'box_count':known.box_count+1})
    except UserError:
        locked=True
    else:
        raise AssertionError('A validated native package permitted a change to its box count')
    ordinary=packages.create({'name':'U46-CONTROL-ORDINARY','is_fruit_tag':False})
    ordinary.write({'name':'U46-CONTROL-RENAMED'})
    normal=[ordinary.name,ordinary.is_fruit_tag,ordinary.step_tag_kind,ordinary.step_tag_state]
    assert normal==['U46-CONTROL-RENAMED',False,False,'created']
    env.cr.rollback()
    return dict(performance=performance,missing=missing,weight_difference=weight_delta,locked=locked,ordinary=normal)

def history_scope(env):
    assert env.cr.dbname in ('COMMUNITY_CERRO_BOM_PACKING_20261127U46A','COMMUNITY_CERRO_BOM_PACKING_20261127U46C')
    actor=env['res.users'].browse(6)
    model=env['step.packing.production'].with_user(actor).with_context(allowed_company_ids=actor.company_ids.ids)
    record=model.search([],limit=1)
    assert record and record.has_access('read')
    operations={'create':lambda: model.create({}),'write':lambda: record.write({'name':record.name}),'unlink':record.unlink}
    denied=[]
    for operation,attempt in operations.items():
        assert not record.has_access(operation)
        try:
            with env.cr.savepoint():
                attempt()
        except AccessError:
            denied.append(operation)
        else:
            raise AssertionError('The historical OT accepted '+operation)
    env.cr.rollback()
    return dict(read=True,denied=denied)
