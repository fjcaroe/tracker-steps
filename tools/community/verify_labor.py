"""Labor operations forms and costs with an existing profile; rollback only."""
from odoo.addons.step_labor_operations_core.ownership import RECORDS

try:
    for name in RECORDS:
        assert env.ref('step_hr.'+name) == env.ref('step_labor_operations_core.'+name),name
    operator=env.ref('base.user_admin') if MODE=='community' else user
    scoped_labor=api.Environment(env.cr,operator.id,dict(env.context,allowed_company_ids=company.ids),su=False)
    assert not scoped_labor.su
    for model,view in [('hr.salary.custom','view_hr_salary_custom_form'),
                       ('step.tarja','view_step_tarja_form'),('hr.contract','step_view_hr_contract_form')]:
        scoped_labor[model].get_view(scoped_labor.ref('step_hr.'+view).id,'form')
    if MODE=='community':
        assert 'payslip_run_id' not in scoped_labor['hr.salary.custom']._fields
        assert not hasattr(scoped_labor['step.tarja'],'envio_nomina')
    employee=scoped_labor['hr.employee'].create({'name':'Private labor verification','company_id':company.id})
    contract=scoped_labor['hr.contract'].create({'name':'Private labor contract verification',
        'employee_id':employee.id,'company_id':company.id,'date_start':'2026-10-01','wage':800000,
        'resource_calendar_id':company.resource_calendar_id.id})
    # Omit explicit type during these reversible native API checks so the
    # legacy create override doesn't consume the customer's SQL sequence.
    # Automatic numbering is exercised separately with isolated company fixtures.
    crew=scoped_labor['hr.salary.custom'].create({'name':'Private crew verification','company_id':company.id})
    crew.write({'group_type':'propio'})
    tarja=scoped_labor['step.tarja'].create({'name':'Private tarja verification','salary_id':crew.id,
        'company_id':company.id,'date':'2026-10-27','tarja_line':[(0,0,{'employee_id':employee.id,
            'contract_id':contract.id,'hrs':1})]})
    assert tarja.tarja_line.hrs_total==1
    tarja.action_auto();tarja.action_costeo();assert tarja.state=='costo'
    scoped_labor['step.movi.registry'].get_view(
        scoped_labor.ref('step_mobilization.view_step_movi_registry_form').id,'form')
    scoped_labor['step.movi.registry'].search_count([])
    print('LABOR_NATIVE_OK '+json.dumps({'uid':operator.id,'company_id':company.id,'su':False,
        'crew_create':True,'tarja_costing':True,'contract_form':True,'mobilization_form':True,
        'legacy_xmlids':len(RECORDS),'numbering':'isolated fixtures only'}))
finally:
    env.cr.rollback()
