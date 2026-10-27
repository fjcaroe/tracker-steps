
import json
from odoo.tools import config
previous_test_enable = config['test_enable']
config['test_enable'] = True
from odoo.tests import Form
config['test_enable'] = previous_test_enable
from odoo.addons.step_accounting_multicurrency_core.hooks import CORE,LEGACY,VIEWS,FIELDS
try:
 for name in VIEWS: assert env.ref(CORE+'.'+name)==env.ref(LEGACY+'.'+name)
 for model,names in FIELDS.items():
  for name in names:
   key='field_'+model.replace('.','_')+'__'+name
   assert env.ref(CORE+'.'+key)==env.ref(LEGACY+'.'+key)
 from odoo.addons.step_treasury_community_reports.hooks import MODULE,LAUNCHERS
 for name,kind,*unused in LAUNCHERS:
  menu=env.ref('step_account_treasury.'+name)
  assert menu==env.ref(MODULE+'.'+name)
  assert menu.action==env.ref(MODULE+'.action_'+kind)
 users=env['res.users'].search([('active','=',True),('share','=',False),('id','!=',1)])
 users=users.filtered(lambda u:u.has_group('account.group_account_manager') and u.has_group('step_account_treasury.group_treasury_reader'))
 assert users,'No existing accounting business user for flow verification'
 environment=globals().get('ENVIRONMENT',MODE)
 if MODE!='community' and environment in ('cerro','qa-cerro'):
  company=env['res.company'].search([('vat','=','76943293-0')])
  assert len(company)==1,'Canonical Cerro company must be unique'
  users=users.filtered(lambda u:company in u.company_ids)
  assert users,'No existing authorized report user for Cerro'
  user=users[:1]
 else:
  user=users[:1];company=user.company_id
 scoped=env(user=user,su=False,context=dict(env.context,allowed_company_ids=company.ids))
 for name,kind,*unused in LAUNCHERS:
  menu=scoped.ref('step_account_treasury.'+name)
  assert menu.id in scoped['ir.ui.menu']._visible_menu_ids()
  report=scoped['step.treasury.report'].create({'kind':kind,'company_id':company.id})
  last=scoped['account.move.line'].search([('company_id','=',company.id),('parent_state','=','posted')],order='date desc',limit=1)
  if last: report.date_to=max(report.date_to,last.date)
  report.date_from=report.date_to.replace(day=1)
  result=report.report_data()
  types=['asset_receivable'] if kind=='receivable' else ['liability_payable'] if kind=='payable' else ['asset_receivable','liability_payable'] if kind=='ledger' else ['asset_cash']
  domain=[('company_id','=',company.id),('parent_state','=','posted'),('date','<=',report.date_to),('account_id.account_type','in',types)]
  measure='amount_residual' if kind in ('receivable','payable') else 'balance'
  total=scoped['account.move.line']._read_group(domain,[],[measure+':sum'])[0][0]
  assert company.currency_id.is_zero(result['closing']-total),'Report does not reconcile to native accounting'
  report.action_calculate();report.action_export()
  assert report.result_html and report.export_file
  Form(report,view=MODULE+'.view_report_form')
 print('COMMUNITY_REPORTS_NATIVE_FLOW_OK five_menus=True exports=True native_totals=True scoped_business_user=True uid=%s company=%s'%(scoped.uid,company.id))
 Form(env['step.cashflow'])
 Form(env['step.treasury.concept'])
 Form(env['account.payment'],view='account.view_account_payment_form')
 ee=env['ir.module.module'].search_count([('state','=','installed'),('license','=','OEEL-1')])
 assert MODE!='community' or ee==0,'Enterprise modules installed in Community runtime'
 print('COMMUNITY_TREASURY_REGISTRY_OK '+json.dumps({'mode':MODE,'enterprise_installed':ee,'same_xmlids':True,'native_form':True,'writes':False}))
finally: env.cr.rollback()
