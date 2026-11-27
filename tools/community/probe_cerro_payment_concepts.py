"""Exercise the original Cerro concept list, product link and valued-program restriction."""
import hashlib
import json

from odoo.exceptions import AccessError, UserError

FIELDS=('name','sequence','company_id','code','notes','date','standard_cost_per_kg',
        'standard_cost_per_box','standard_cost_per_pallet')
MODEL='step.export.payment.concept'
STUDIO='studio_customization.odoo_studio_step_exp_190b5787-3bb7-4f94-b7cb-b1b9a20d75cd'


def digest(payload):
    return hashlib.sha256(json.dumps(payload,sort_keys=True,default=str).encode()).hexdigest()


def exercise(env):
    actor=env['res.users'].browse(6)
    scopes=sorted(actor.company_ids.ids)
    concepts=env[MODEL].with_user(actor).with_context(allowed_company_ids=scopes)
    assert not concepts.env.su and env.ref(STUDIO).id==4845
    assert (env.ref('step_export.action_step_export_payment_concept').id,
            env.ref('step_export.menu_step_export_payment_concept').id)==(1378,987)
    spec={field:{} for field in FIELDS}
    scopes_receipt={}
    for selected in [[i] for i in scopes]+[scopes]:
        subset=concepts.with_context(allowed_company_ids=selected)
        rows=subset.web_search_read([],specification=spec,limit=20,order='id')['records']
        assert len(rows)==6
        scopes_receipt[','.join(map(str,selected))]=digest(rows)
    operators={}
    for user in env['res.users'].sudo().search([('active','=',True),('share','=',False)],order='id'):
        if user.id==1:
            continue
        user_model=env[MODEL].with_user(user).with_context(allowed_company_ids=user.company_ids.ids)
        allowed={operation:user_model.has_access(operation) for operation in ('read','create','write','unlink')}
        if allowed['read']:
            allowed['visible_rows']=len(user_model.search([]))
        operators[str(user.id)]=allowed
    public=concepts.with_user(env.ref('base.public_user'))
    try:
        public.check_access('read')
    except AccessError:
        pass
    else:
        raise AssertionError('The public actor can read payment concepts')
    owner=env['res.company'].browse(2)
    company=concepts.with_context(allowed_company_ids=[owner.id])
    new,=company.web_save({'name':'Prueba privada concepto de pago','code':'QA_CONCEPTO',
                           'company_id':owner.id,'standard_cost_per_kg':12.3456},spec)
    record=company.browse(new['id'])
    assert record.standard_cost_per_kg==12.3456
    linked=env['product.template'].with_user(actor).with_context(allowed_company_ids=scopes).search(
        [('step_export_payment_concept_id','!=',False)],order='id')
    assert len(linked)==2
    before=linked.read(['step_export_payment_concept_id'],load=None)
    assignments=digest(before)
    linked[0].write({'step_export_payment_concept_id':record.id})
    assert linked[0].step_export_payment_concept_id==record
    env.flush_all()
    # The native copy has ten sales programmes, with no historical packaging
    # programme or costs. Reserve negative fixture IDs to leave sequences intact.
    env.cr.execute('SELECT id FROM step_export_sales_program WHERE company_id=%s ORDER BY id LIMIT 1',(owner.id,))
    sales,=env.cr.fetchone()
    env.cr.execute("INSERT INTO step_export_packaging_program(id,sales_program_id,company_id,name,state) VALUES (-45001,%s,%s,'Prueba aislada','draft')",(sales,owner.id))
    env.cr.execute('INSERT INTO step_export_packaging_cost(id,program_id,concept_id) VALUES (-45001,-45001,%s)',(record.id,))
    record.web_save({'standard_cost_per_box':4.4321},spec)
    assert record.standard_cost_per_box==4.4321
    env.cr.execute("UPDATE step_export_packaging_program SET state='valued' WHERE id=-45001")
    env.invalidate_all()
    refusals=[]
    for name in FIELDS[-3:]:
        try:
            with env.cr.savepoint():
                record.web_save({name:8.7654},spec)
        except UserError as err:
            refusals.append(type(err).__name__)
        else:
            raise AssertionError('The cost of a valued programme changed')
    assert refusals==['UserError']*3
    another=next(pk for pk in scopes if pk!=owner.id)
    remote=record.with_context(allowed_company_ids=[another])
    remote.web_save({'standard_cost_per_pallet':2.7182},spec)
    assert remote.standard_cost_per_pallet==2.7182
    env.cr.rollback()
    env.invalidate_all(flush=False)
    assert not record.exists() and linked.read(['step_export_payment_concept_id'],load=None)==before
    return dict(uid=actor.id,contexts=scopes_receipt,operators=operators,product_links=assignments,linked_products=len(linked),
                draft_write=True,valued_refusals=refusals,public_denied=True)
