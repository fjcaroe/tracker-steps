import json
try:
    Model = env['account.analytic.account']
    print(json.dumps({name: {'compute': Model._fields[name].compute, 'default_type': type(Model._fields[name].default).__name__, 'precompute': Model._fields[name].precompute} for name in ('farm','species','variety','hectares','plants','cost_type')}))
    farm = env['step.fundo'].create({'name':'QA probe farm','company_id':env.company.id})
    account = Model.create({'name':'QA probe center','plan_id':env['account.analytic.plan'].search([],limit=1).id,
        'company_id':env.company.id,'fundo_id':farm.id,'type_costo':'fruta','etapa_costo':'ope','tipo_fruta':'conven','has_cost':10,'plant_cost':500})
    print(json.dumps({'before':{'farm':account.farm,'fundo_name':account.fundo_id.name,'hectares':account.hectares,'plants':account.plants}}))
    account._compute_management_from_agriculture()
    print(json.dumps({'after':{'farm':account.farm,'hectares':account.hectares,'plants':account.plants}}))
    season = env['step.temporada'].create({'name':'QA probe shared','company_ids':[(5,0,0)]})
    print(json.dumps({'shared_company_id':season.company_id.id,'shared_company_ids':season.company_ids.ids}))
finally:
    env.cr.rollback()
    print('PROBE_ROLLBACK_OK')
