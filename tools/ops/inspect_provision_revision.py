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
        if 'entry_amount_clp' in p.line_ids._fields:
            print('PREVIEW',json.dumps({'id':p.id,'total_clp':p.amount_clp,'total_usd':p.amount_usd,
                'lines':[{'id':line.id,'currency':line.currency_id.name,'amount':line.amount_currency,
                    'clp':line.entry_amount_clp,'usd':line.entry_amount_usd,'warning':line.exchange_rate_warning}
                    for line in p.line_ids]},default=str))
    for plan in env['account.analytic.plan'].search([]):
        print('PLAN',plan.id,plan.name,plan.root_id.id)
    print('ACCOUNT_COUNTS', [(p.id,env['account.analytic.account'].search_count([('plan_id','=',p.id)])) for p in env['account.analytic.plan'].search([])])
    print('RATE_COUNTS',[(c.name,env['res.currency.rate'].search_count([('currency_id','=',c.id)])) for c in env.ref('base.CLP')|env.ref('base.USD')])
    for p in env['step.export.shipment.provision'].search([],order='id desc',limit=10):
        journal=p.journal_id
        print('COST_CONFIGURATION',json.dumps({'provision':p.id,'company':p.company_id.id,
            'journal':{'id':journal.id,'name':journal.name,'default_account':journal.default_account_id.id},
            'products':[{'id':line.product_id.id,'name':line.product_id.name,
                'expense_account':(line.product_id.with_company(p.company_id).property_account_expense_id or
                    line.product_id.categ_id.with_company(p.company_id).property_account_expense_categ_id).id}
                for line in p.line_ids]},default=str))
        print('GENERAL_JOURNALS',[(j.id,j.name,j.default_account_id.id) for j in env['account.journal'].search([('company_id','=',p.company_id.id),('type','=','general')])])
        print('LIABILITY_ACCOUNTS',[(account.id,account.code,account.name,account.account_type) for account in env['account.account'].with_company(p.company_id).search([('company_ids','in',p.company_id.ids),('deprecated','=',False),('account_type','in',['liability_current','liability_non_current','liability_payable'])])])
    for p in env['step.export.shipment.provision'].search([],order='id desc',limit=1):
        plans=env['account.analytic.plan'].search([('name','in',['Embarque','Project','Proyecto','Temporada'])])
        print('AVAILABLE_ACCOUNTS',[(a.id,a.name,a.plan_id.name,a.company_id.id) for a in env['account.analytic.account'].search([
            ('root_plan_id','in',plans.root_id.ids),('active','=',True),'|',('company_id','=',False),('company_id','=',p.company_id.id)])])
finally:
    env.cr.rollback()
