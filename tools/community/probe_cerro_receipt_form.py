"""Read the auxiliary fields of the original receipt form for its actual operators and company scopes."""
from datetime import date
import hashlib
import json

from odoo.exceptions import AccessError

from probe_cerro_picking_lists import user_models

STOCK=('check_ids','quality_check_fail','quality_alert_count','dispatch_guide_count','step_container_work_order_id',
       'step_dispatch_origin_guide_id','step_interplant_guide_id','step_interplant_tag_ids','step_product_correction_count',
       'l10n_cl_delivery_guide_reason','l10n_cl_draft_status','l10n_cl_dte_file','l10n_cl_is_return',
       'l10n_cl_sii_send_file','l10n_cl_sii_send_ident','l10n_latam_document_type_id')
MODELS={'stock.picking':(*STOCK,'dispatch_guide_ids','quality_alert_ids','step_product_correction_move_ids'),
    'stock.quant.package':('step_interplant_origin_tag_id',),
    'step.dispatch.guide':('name','picking_id','company_id','date'),
    'step.harvest.container.work.order':('name','company_id'),
    'quality.alert':('name','company_id','picking_id'),
    'quality.check':('name','company_id','quality_state','picking_id','point_id'),
    'quality.point':('name','company_id')}
PARAMS=('string','help','type','comodel_name','inverse_name','copy','readonly','required','store','index','tracking','ondelete','groups','translate')


def digest(rows):
    return hashlib.sha256(json.dumps(rows,sort_keys=True,default=str).encode()).hexdigest()


def capture(env):
    assert env.cr.dbname=='MANAGEMENT_QA_CERRO_BOM_20261126U42N' or env.cr.dbname.startswith('COMMUNITY_CERRO_BOM_PACKING_20261127U46')
    descriptions={}
    for model,names in MODELS.items():
        obj=env[model]
        info={}
        for name in names:
            if name not in obj._fields:
                continue
            field=obj._fields[name]
            details={key:getattr(field,key,None) for key in PARAMS}
            details['default']=field.default(obj) if field.default else None
            if isinstance(details['default'],date):
                details['default']='current_date' if details['default']==date.today() else details['default'].isoformat()
            if hasattr(details['default'],'ids'):
                details['default']=details['default'].ids
            if field.type=='selection':
                details['choices']=field._description_selection(env)
            info[name]=details
        descriptions[model]=dict(fields=info,order=obj._order,rec_name=obj._rec_name,description=obj._description)
    contexts={}
    for (uid,scope),model in user_models(env):
        key=str(uid)+'/'+','.join(map(str,scope))
        try:
            with env.cr.savepoint():
                rows=model.search([],order='id').read(list(STOCK),load=None)
                contexts[key]=dict(count=len(rows),sha256=digest(rows),
                    filled={name:sum(bool(row[name]) for row in rows) for name in STOCK})
        except AccessError:
            contexts[key]=dict(denied=True)
    env.cr.rollback()
    return dict(descriptions=descriptions,contexts=contexts)

def operations(env):
    assert env.cr.dbname=='MANAGEMENT_QA_CERRO_BOM_20261126U42N' or env.cr.dbname.startswith('COMMUNITY_CERRO_BOM_PACKING_20261127U46')
    actor=env['res.users'].browse(6)
    model=env['stock.picking'].with_user(actor).with_context(allowed_company_ids=actor.company_ids.ids,lang='en_US')
    reports={}
    for item in model.search([],order='id'):
        for field,method in [('step_product_correction_count','action_step_view_product_corrections'),
                             ('dispatch_guide_count','action_view_dispatch_guides')]:
            if not item[field]:
                continue
            action=getattr(item,method)()
            records=model.env[action['res_model']].search(action['domain'],order='id')
            assert len(records)==item[field]
            reports.setdefault(field,[]).append([item.id,action['res_model'],len(records),digest(records.ids)])
    returns=model.search([]).filtered('l10n_cl_is_return')
    views={}
    for typ in ('incoming','internal','outgoing'):
        candidate=model.search([('picking_type_code','=',typ),('return_id','=',False),('move_ids','!=',False)],order='id',limit=1)
        if not candidate:
            continue
        move=candidate.move_ids.sorted('id')[:1]
        other=model.search([('id','!=',candidate.id),('company_id','=',candidate.company_id.id),('move_ids','!=',False)],order='id',limit=1)
        if not move or not other.move_ids:
            continue
        seen={}
        for label,parent,origin in [('ordinary',False,False),('return_order',True,False),
                                  ('returned_move',False,True),('both',True,True)]:
            env.cr.execute('UPDATE stock_picking SET return_id=%s WHERE id=%s',(other.id if parent else None,candidate.id))
            env.cr.execute('UPDATE stock_move SET origin_returned_move_id=%s WHERE id=%s',
                           (other.move_ids.sorted('id')[0].id if origin else None,move.id))
            env.invalidate_all(flush=False)
            seen[label]=candidate.l10n_cl_is_return
        views[typ]=seen
    mixed=model.search([],order='id').filtered(lambda item:len(item.move_ids)>=2)[:1]
    if mixed:
        moves=mixed.move_ids.sorted('id')
        origin=model.search([('company_id','=',mixed.company_id.id),('id','!=',mixed.id),('move_ids','!=',False)],limit=1).move_ids[:1]
        views['mixed']={}
        for name,records in [('none',moves[:0]),('first',moves[:1]),('last',moves[-1:]),('all',moves)]:
            env.cr.execute('UPDATE stock_move SET origin_returned_move_id=NULL WHERE id=ANY(%s)',(moves.ids,))
            if records:
                env.cr.execute('UPDATE stock_move SET origin_returned_move_id=%s WHERE id=ANY(%s)',(origin.id,records.ids))
            env.invalidate_all(flush=False)
            views['mixed'][name]=mixed.l10n_cl_is_return
    env.cr.rollback()
    return dict(reports=reports,return_count=len(returns),return_ids=digest(sorted(returns.ids)),return_cases=views)

def quality(env):
    assert env.cr.dbname=='MANAGEMENT_QA_CERRO_BOM_20261126U42N' or env.cr.dbname.startswith('COMMUNITY_CERRO_BOM_PACKING_20261127U46')
    user=env['res.users'].browse(6)
    model=env['stock.picking'].with_user(user).with_context(allowed_company_ids=user.company_ids.ids)
    result={}
    for state in ('assigned','done','cancel'):
        item=model.search([('state','=',state)],limit=1,order='id')
        if not item:
            continue
        home=item.company_id.id
        foreign=(user.company_ids-item.company_id)[:1].id
        env.cr.execute("""INSERT INTO quality_point (id,company_id,measure_on,test_type_id,team_id,name,test_report_type,measure_frequency_type)
                       VALUES (-460501,%s,'operation',(SELECT min(id) FROM quality_point_test_type),(SELECT min(id) FROM quality_alert_team),'QA','pdf','all')""",(home,))
        env.cr.execute("""INSERT INTO quality_check (id,company_id,measure_on,test_type_id,team_id,picking_id,quality_state)
                       VALUES (-460501,%s,'operation',(SELECT min(id) FROM quality_point_test_type),(SELECT min(id) FROM quality_alert_team),%s,'none')""",(home,item.id))
        env.cr.execute("""INSERT INTO quality_alert (id,company_id,team_id,picking_id) VALUES
                       (-460501,%s,(SELECT min(id) FROM quality_alert_team),%s)""",(home,item.id))
        for label,value,company,point in [('pending','none',home,None),('passed','pass',home,None),('failed','fail',home,None),
                                         ('foreign','fail',foreign,None),('native_point','fail',foreign,-460501)]:
            env.cr.execute('UPDATE quality_check SET quality_state=%s,company_id=%s,point_id=%s WHERE id=-460501',(value,company,point))
            env.cr.execute('UPDATE quality_alert SET company_id=%s WHERE id=-460501',(company,))
            env.invalidate_all(flush=False)
            for actor,scope in [(6,[home]),(6,[home,foreign]),(34,[home])]:
                dst=env['stock.picking'].with_user(actor).with_context(allowed_company_ids=scope).browse(item.id)
                key=state+'/'+label+'/'+str(actor)+'/'+','.join(map(str,scope))
                try:
                    with env.cr.savepoint():
                        row=dst.read(['check_ids','quality_alert_count','quality_check_fail'],load=None)[0]
                        result[key]=[sorted(row['check_ids']),row['quality_alert_count'],row['quality_check_fail']]
                except AccessError:
                    result[key]=dict(denied=True)
        env.cr.rollback()
    return result
