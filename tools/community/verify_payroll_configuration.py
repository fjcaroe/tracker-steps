"""Run through Odoo shell in a private Community rehearsal; rollback all fixtures."""
import json
import os
from pathlib import Path
from lxml import etree
from datetime import datetime, time, timedelta
from odoo import api, Command, fields

assert env.cr.dbname.startswith('COMMUNITY_PAYROLL_API_')
assert not env['ir.module.module'].search_count([('state','=','installed'),('license','=','OEEL-1')])
output=Path(os.environ['PAYROLL_CONFIGURATION_EVIDENCE'])
assert str(output.resolve()).startswith('/opt/steps-validation/')
try:
    company=env['res.company'].create({'name':'Private configuration rehearsal','currency_id':env.ref('base.CLP').id})
    actor=env['res.users'].with_context(no_reset_password=True).create({
        'name':'Private configuration manager','login':'private-payroll-configuration-manager',
        'company_id':company.id,'company_ids':[Command.set(company.ids)],
        'groups_id':[Command.set([env.ref(g).id for g in ('base.group_user','payroll.group_payroll_manager','hr.group_hr_manager')])]})
    scoped=api.Environment(env.cr,actor.id,dict(env.context,allowed_company_ids=company.ids),su=False)
    menu=scoped.ref('payroll.hr_payroll_structure_menu')
    visible=scoped['ir.ui.menu']._visible_menu_ids()
    cursor=menu
    chain=[]
    while cursor:
        assert cursor.id in visible
        chain.append(cursor.id)
        cursor=cursor.parent_id
    assert menu.action.res_model=='hr.payroll.structure'
    form=scoped['hr.payroll.structure'].get_view(scoped.ref('payroll.hr_payroll_structure_view_form').id,'form')
    arch=etree.fromstring(form['arch'])
    required=('type_id','use_work_entries','out_of_contract_work_entry_type_id','step_clp_concept_rounding')
    assert all(arch.xpath("//field[@name='%s']"%name) for name in required)
    kind=scoped['hr.payroll.structure.type'].create({'name':'Private configuration type'})
    structure=scoped['hr.payroll.structure'].create({'name':'Private configuration structure','code':'PAPI_CONFIG',
        'company_id':company.id,'parent_id':False,'type_id':kind.id,
        'use_work_entries':True,'step_clp_concept_rounding':True})
    assert structure.use_work_entries and structure.step_clp_concept_rounding
    assert not structure.env.su
    calendar=scoped['resource.calendar'].create({'name':'Private UI calendar','company_id':company.id,'tz':'UTC'})
    employee=scoped['hr.employee'].create({'name':'Private UI employee','company_id':company.id,'resource_calendar_id':calendar.id})
    employee.resource_id.tz='UTC'
    first=fields.Date.today().replace(day=1)
    contract=scoped['hr.contract'].create({'name':'Private UI contract','employee_id':employee.id,'company_id':company.id,
        'date_start':first,'state':'open','wage':1000,'resource_calendar_id':calendar.id,'struct_id':structure.id,'structure_type_id':kind.id})
    work_type=scoped['hr.work.entry.type'].create({'name':'Private UI attendance','code':'PAPI_UI'})
    monday=first+timedelta(days=(-first.weekday())%7)
    scoped['hr.work.entry'].create({'name':'Private UI work entry','employee_id':employee.id,'company_id':company.id,
        'contract_id':contract.id,'work_entry_type_id':work_type.id,
        'date_start':datetime.combine(monday,time(8)),'date_stop':datetime.combine(monday,time(12))})
    # Actual unsaved form records exercise native onchanges; no substitute model.
    draft=scoped['hr.payslip'].with_context(contract=True).new({'employee_id':employee.id,'company_id':company.id,
        'contract_id':contract.id,'struct_id':structure.id,'date_from':first,'date_to':fields.Date.today()})
    draft.onchange_employee()
    assert draft.worked_days_line_ids.work_entry_type_id==work_type
    assert draft.worked_days_line_ids.number_of_hours==4
    result={'menu_visible':True,'menu_chain':chain,'action_model':menu.action.res_model,
        'form_fields':list(required),'configuration_saved_with_normal_permissions':True,
        'native_payroll_form_onchange':True,'actor_sudo':False,'fixtures_rolled_back':True}
finally:
    env.cr.rollback()
output.write_text(json.dumps(result,indent=2),encoding='utf-8')
print('PAYROLL_CONFIGURATION_OK')
