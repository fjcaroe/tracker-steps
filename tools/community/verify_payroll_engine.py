"""Native OCA calculation/accounting candidate proof; not a Chile payroll certification."""
import json
from odoo import api, Command, fields

try:
    assert not env['ir.module.module'].search_count([('license','=','OEEL-1'),('state','=','installed')])
    requirements=[('hr.payroll.structure.type',None),('hr.payslip.input.type',None),
                  ('hr.payslip.input','input_type_id'),('hr.payslip.worked_days','work_entry_type_id'),
                  ('hr.payroll.structure','type_id'),('hr.salary.rule','struct_id'),
                  ('hr.contract','structure_type_id'),('hr.payslip','_get_line_values'),
                  ('hr.payslip','_get_worked_day_lines_values')]
    missing=[]
    for model,member in requirements:
        if model not in env.registry.models or member and member not in env[model]._fields and not hasattr(env[model],member):
            missing.append(model+('.'+member if member else ''))
    company=env['res.company'].create({'name':'Private Community engine fixture'})
    operator=env['res.users'].with_context(no_reset_password=True).create({
        'name':'Private real payroll operator','login':'private-oca-engine-operator',
        'company_id':company.id,'company_ids':[Command.set(company.ids)],
        'groups_id':[Command.set([env.ref(g).id for g in ('base.group_user',
            'payroll.group_payroll_manager','account.group_account_manager')])]})
    scoped=api.Environment(env.cr,operator.id,dict(env.context,allowed_company_ids=company.ids),su=False)
    assert not scoped.su
    debit=scoped['account.account'].create({'name':'Private payroll cost','code':'930001',
        'account_type':'expense','company_ids':[Command.set(company.ids)]})
    credit=scoped['account.account'].create({'name':'Private payroll payable','code':'930002',
        'account_type':'liability_current','company_ids':[Command.set(company.ids)]})
    journal=scoped['account.journal'].create({'name':'Private payroll journal','code':'PQA','type':'general',
        'company_id':company.id})
    category=scoped['hr.salary.rule.category'].create({'name':'Private net','code':'PRIVATE_NET','company_id':company.id})
    rule=scoped['hr.salary.rule'].create({'name':'Private real salary rule','code':'PRIVATE_NET','sequence':1,
        'category_id':category.id,'company_id':company.id,'condition_select':'none','amount_select':'code',
        'amount_python_compute':'result = contract.wage + inputs.PRIVATE_BONUS.amount',
        'account_debit':debit.id,'account_credit':credit.id})
    structure=scoped['hr.payroll.structure'].create({'name':'Private real structure','code':'PRIVATE',
        'company_id':company.id,'parent_id':False,'rule_ids':[Command.set(rule.ids)]})
    employee=scoped['hr.employee'].create({'name':'Private real employee','company_id':company.id})
    contract=scoped['hr.contract'].create({'name':'Private real contract','employee_id':employee.id,
        'company_id':company.id,'date_start':fields.Date.today().replace(day=1),'wage':800000,
        'struct_id':structure.id,'journal_id':journal.id,'state':'open'})
    run=scoped['hr.payslip.run'].create({'name':'Private real run','company_id':company.id,'struct_id':structure.id})
    slip=scoped['hr.payslip'].create({'name':'Private real slip','employee_id':employee.id,
        'company_id':company.id,'contract_id':contract.id,'struct_id':structure.id,'payslip_run_id':run.id,
        'date_from':fields.Date.today().replace(day=1),'date_to':fields.Date.today()})
    scoped['hr.payslip.input'].create({'name':'Private real input','code':'PRIVATE_BONUS',
        'payslip_id':slip.id,'contract_id':contract.id,'amount':123.45})
    slip.compute_sheet()
    total=slip.get_salary_line_total('PRIVATE_NET')
    assert abs(total-800123.45)<0.001,total
    slip.action_payslip_done()
    assert slip.state=='done' and slip.move_id
    assert abs(sum(slip.move_id.line_ids.mapped('balance')))<0.001
    assert sum(slip.move_id.line_ids.mapped('debit'))==company.currency_id.round(total)
    for model in ('hr.payslip','hr.contract','hr.payroll.structure'):
        assert scoped[model].get_view(view_type='form')['arch']
    assert scoped.ref('payroll.hr_payslip_menu').id in scoped['ir.ui.menu']._visible_menu_ids()
    print('PAYROLL_ENGINE_NATIVE_OK '+json.dumps({'uid':operator.id,'su':False,
        'calculation':total,'account_move':True,'balanced':True,'forms_menu':True,
        'simpledigital_compatible':False,'missing_required_api':missing,
        'chilean_rules_certified':False,'historical_paid_conversion':False}))
finally:
    env.cr.rollback()
