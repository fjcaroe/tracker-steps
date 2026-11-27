"""Read the delivery and reception lists under historical users and exercise pending quality checks."""
import hashlib
import json

from odoo.exceptions import AccessError


NATIVE = 'MANAGEMENT_QA_CERRO_BOM_20261126U42N'
CANDIDATE = 'COMMUNITY_CERRO_BOM_PACKING_20261127U46A'
COLD = 'COMMUNITY_CERRO_BOM_PACKING_20261127U46B'
FINAL='COMMUNITY_CERRO_BOM_PACKING_20261127U46C'
RECEIPT='COMMUNITY_CERRO_BOM_PACKING_20261127U46D'
FISCAL = ['l10n_latam_document_number', 'l10n_cl_dte_status']
SUMMARY = ['step_external_reception_folio', 'step_reception_container_qty', 'step_reception_net_kg',
           'step_reception_avg_kg', 'step_reception_product_ids', 'step_reception_packaging_ids']
FIELDS = ['state', *FISCAL, 'quality_check_todo', *SUMMARY]


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def user_models(env):
    users = env['res.users'].search([('share', '=', False), ('active', '=', True), ('id', '!=', 1)], order='id')
    for user in users:
        companies = sorted(user.company_ids.ids)
        for scope in [companies, *([cid] for cid in companies if len(companies)>1)]:
            yield (user.id, tuple(scope)), env['stock.picking'].with_user(user).with_context(
                allowed_company_ids=scope, lang='en_US')


def exercise(env):
    assert env.cr.dbname in (NATIVE, CANDIDATE, COLD, FINAL, RECEIPT)
    models = dict(user_models(env))
    outcome = {}
    for (uid, scope), model in models.items():
        key = str(uid) + '/' + ','.join(map(str,scope))
        try:
            with env.cr.savepoint():
                rows = model.search_read([], fields=FIELDS, order='id')
                for row in rows:
                    for field in ('step_reception_product_ids','step_reception_packaging_ids'):
                        row[field] = sorted(row[field])
                outcome[key] = dict(count=len(rows), sha256=digest(rows))
        except AccessError:
            outcome[key] = dict(denied=True)
    actor = env['res.users'].browse(6)
    stock = models[6, tuple(sorted(actor.company_ids.ids))]
    positive = {}
    controls = [stock.search([('state','=',status)], limit=1, order='id') for status in ('draft','assigned','done')]
    assert all(controls)
    env.cr.execute("SELECT count(*) FROM quality_check")
    assert env.cr.fetchone() == (0,)
    for check_id, picking in enumerate(controls, start=101):
        other_company = (actor.company_ids - picking.company_id)[:1]
        assert other_company
        env.cr.execute("""INSERT INTO quality_check (id,company_id,measure_on,test_type_id,team_id,picking_id,quality_state)
            VALUES (%s,%s,'operation',(SELECT min(id) FROM quality_point_test_type),
                    (SELECT min(id) FROM quality_alert_team),%s,'none')""", (-check_id,picking.company_id.id,picking.id))
        env.cr.execute("UPDATE stock_picking SET l10n_latam_document_number=%s,l10n_cl_dte_status='accepted' WHERE id=%s",
                       ('U46-'+str(check_id),picking.id))
        env.cr.execute("""INSERT INTO quality_point (id,company_id,measure_on,test_type_id,team_id,name,test_report_type,measure_frequency_type)
            VALUES (%s,%s,'operation',(SELECT min(id) FROM quality_point_test_type),
                    (SELECT min(id) FROM quality_alert_team),'U46','pdf','all')""",(-check_id,picking.company_id.id))
        entries = {}
        for label, state, company in [('pending','none',picking.company_id), ('passed','pass',picking.company_id),
                                      ('failed','fail',picking.company_id), ('foreign','none',other_company),
                                      ('control_company','none',other_company)]:
            env.cr.execute("UPDATE quality_check SET quality_state=%s, company_id=%s, point_id=%s WHERE id=%s",
                           (state,company.id,-check_id if label=='control_company' else None,-check_id))
            reads = {}
            for (uid,scope), model in models.items():
                env.invalidate_all(flush=False)
                key = str(uid)+'/'+','.join(map(str,scope))
                try:
                    with env.cr.savepoint():
                        row = model.browse(picking.id).read([*FISCAL,'quality_check_todo'])[0]
                    reads[key] = [row[name] for name in [*FISCAL,'quality_check_todo']]
                    if uid==6:
                        for op in ('=','!='):
                            for flag in (True,False):
                                try:
                                    with env.cr.savepoint():
                                        found=model.search_count([('id','=',picking.id),('quality_check_todo',op,flag)])
                                    reads[key].append(found)
                                except (ValueError,NotImplementedError,AccessError) as exc:
                                    reads[key].append(type(exc).__name__)
                except AccessError:
                    reads[key] = 'denied'
            entries[label] = reads
        positive[picking.state] = entries
    env.cr.rollback()
    return dict(history=outcome, checks=positive)

def search_cases(env):
    assert env.cr.dbname in (NATIVE,CANDIDATE,COLD,FINAL,RECEIPT)
    actor=env['res.users'].browse(6)
    all_companies=actor.company_ids
    model=env['stock.picking'].with_user(actor).with_context(allowed_company_ids=all_companies.ids)
    picking=model.search([('state','=','assigned')],limit=1,order='id')
    home=picking.company_id.id
    other=(all_companies-picking.company_id)[:1].id
    scoped=model.with_context(allowed_company_ids=[home])
    probes={'empty':[], 'visible_pending':[(home,'none')], 'visible_finished':[(home,'pass')],
            'hidden_pending':[(other,'none')], 'hidden_finished':[(other,'pass')],
            'mixed_visible':[(home,'none'),(home,'pass')], 'mixed_hidden':[(other,'none'),(other,'pass')],
            'visible_finished_hidden_pending':[(home,'pass'),(other,'none')],
            'visible_pending_hidden_finished':[(home,'none'),(other,'pass')]}
    env.cr.execute('SELECT count(*) FROM quality_check')
    assert env.cr.fetchone()==(0,)
    result={}
    for name,checks in probes.items():
        env.cr.execute("DELETE FROM quality_check WHERE id IN(-901,-902)")
        assert env.cr.rowcount<=2
        for index,(company,status) in enumerate(checks,901):
            env.cr.execute("""INSERT INTO quality_check(id,picking_id,company_id,measure_on,team_id,test_type_id,quality_state)
                VALUES(%s,%s,%s,'operation',(SELECT min(id) FROM quality_alert_team),
                       (SELECT min(id) FROM quality_point_test_type),%s)""",(-index,picking.id,company,status))
        results={}
        for scope,obj in [('all',model),('single',scoped)]:
            env.invalidate_all(flush=False)
            results[scope]=[obj.browse(picking.id).quality_check_todo]
            for operator,value in [('=',True),('=',False),('!=',True),('!=',False)]:
                results[scope].append(obj.search_count([('id','=',picking.id),('quality_check_todo',operator,value)]))
        if env.cr.dbname!=NATIVE:
            env.invalidate_all(flush=False)
            two=model.with_context(allowed_company_ids=[home,other]).browse(picking.id)
            one=scoped.browse(picking.id)
            assert [two.quality_check_todo,one.quality_check_todo,two.quality_check_todo]==[
                results['all'][0],results['single'][0],results['all'][0]]
        result[name]=results
    env.cr.rollback()
    return result
