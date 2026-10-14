"""Read provision linkage and currency support; no writes or credentials."""
import json
try:
    print('VERSIONS', [(m.name,m.latest_version,m.state) for m in env['ir.module.module'].search([('name','in',['step_export_shipment_provision','step_export_shipping_design'])])])
    print('ANALYTIC_RELATIONS', [(n,f.comodel_name) for n,f in env['account.analytic.account']._fields.items() if f.type=='many2one' and f.comodel_name.startswith('step.')])
    for p in env['step.export.shipment.provision'].search([],order='id desc',limit=10):
        print('PROVISION',json.dumps({'id':p.id,'state':p.state,'date':str(p.date),'company':p.company_id.id,
            'season':p.season_id.id,'species':p.species_id.id,'shipment':p.shipment_id.id,
            'season_account':p.season_id.cost_id.id,'species_account':p.species_id.cost_id.id,
            'shipment_account':p.shipment_id.provision_analytic_account_id.id,
            'line_currencies':p.line_ids.currency_id.mapped('name')},default=str))
    for plan in env['account.analytic.plan'].search([]):
        print('PLAN',plan.id,plan.name,plan.root_id.id)
    print('ACCOUNT_COUNTS', [(p.id,env['account.analytic.account'].search_count([('plan_id','=',p.id)])) for p in env['account.analytic.plan'].search([])])
    print('RATE_COUNTS',[(c.name,env['res.currency.rate'].search_count([('currency_id','=',c.id)])) for c in env.ref('base.CLP')|env.ref('base.USD')])
    for p in env['step.export.shipment.provision'].search([],order='id desc',limit=1):
        plans=env['account.analytic.plan'].search([('name','in',['Embarque','Project','Proyecto','Temporada'])])
        print('AVAILABLE_ACCOUNTS',[(a.id,a.name,a.plan_id.name,a.company_id.id) for a in env['account.analytic.account'].search([
            ('root_plan_id','in',plans.root_id.ids),('active','=',True),'|',('company_id','=',False),('company_id','=',p.company_id.id)])])
finally:
    env.cr.rollback()
